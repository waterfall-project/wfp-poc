# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Resource endpoints.

Implements CRUD operations for resources with authentication,
authorization, validation, and pagination.
"""

import math
import uuid
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.assignment import Assignment
from app.models.db import db
from app.models.resource import Resource as ResourceModel
from app.schemas.resource_schema import (
    ResourceCreateSchema,
    ResourceListResponseSchema,
    ResourceResponseSchema,
    ResourceSchema,
    ResourceUpdateSchema,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    get_current_user_id,
    require_jwt_auth,
)

# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"

# Error Messages
INVALID_PAGINATION_MSG = "Invalid pagination parameters"
INVALID_SORT_BY_MSG = "Invalid sort_by: {sort_by}"
INVALID_SORT_ORDER_MSG = "Invalid sort_order: {sort_order}"
INVALID_TYPE_MSG = "Invalid type: {resource_type}"
INVALID_IS_ACTIVE_MSG = "Invalid is_active value: {value}"
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
RESOURCE_NOT_FOUND_MSG = "Resource not found"
DUPLICATE_RESOURCE_NAME_MSG = "Resource name already exists for this company"
CANNOT_DELETE_WITH_ASSIGNMENTS_MSG = (
    "Cannot delete resource with {count} active assignments"
)

# Success Messages
RESOURCE_CREATED_MSG = "Resource created successfully"
RESOURCE_UPDATED_MSG = "Resource updated successfully"


def _rate_limit_user_key() -> str:
    """Rate limiting key based on authenticated user."""
    user_id = get_current_user_id()
    if user_id:
        return str(user_id)
    return request.remote_addr or "anonymous"


def _parse_bool_param(value: str | None) -> tuple[bool | None, dict[str, Any] | None]:
    """Parse boolean-like query parameter values."""
    if value is None:
        return None, None

    normalized = value.strip().lower()
    if normalized in ["true", "1", "yes"]:
        return True, None
    if normalized in ["false", "0", "no"]:
        return False, None

    return None, {
        "error": BAD_REQUEST_ERROR,
        "message": INVALID_IS_ACTIVE_MSG.format(value=value),
    }


def _get_resource(resource_id: str) -> ResourceModel | None:
    """Retrieve a resource scoped to the current company."""
    try:
        resource_uuid = uuid.UUID(resource_id)
    except ValueError:
        return None

    company_id = get_current_company_id()
    return ResourceModel.query.filter_by(
        id=resource_uuid, company_id=company_id
    ).first()


class ResourceListResource(Resource):
    """REST resource for collection operations on resources."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.resource_schema = ResourceSchema()
        self.response_schema = ResourceResponseSchema()
        self.list_schema = ResourceListResponseSchema()
        self.create_schema = ResourceCreateSchema()
        self.update_schema = ResourceUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.LIST, "resources")
    @limiter.limit("100 per minute", key_func=_rate_limit_user_key)
    def get(self, version: str | None = None) -> tuple[dict, int]:
        """List resources for the authenticated company with pagination."""
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        company_id = get_current_company_id()

        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_PAGINATION_MSG,
            }, 400

        query = ResourceModel.query.filter_by(company_id=company_id)

        resource_type = request.args.get("type")
        if resource_type:
            if resource_type not in ["labor", "material", "cost"]:
                return {
                    "error": BAD_REQUEST_ERROR,
                    "message": INVALID_TYPE_MSG.format(resource_type=resource_type),
                }, 400
            query = query.filter(ResourceModel.type == resource_type)

        is_active_param = request.args.get("is_active")
        is_active, error = _parse_bool_param(is_active_param)
        if error:
            return error, 400
        if is_active is not None:
            query = query.filter(ResourceModel.is_active == is_active)

        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                ResourceModel.name.ilike(search_pattern)
                | func.coalesce(ResourceModel.email, "").ilike(search_pattern)
            )

        sort_by = request.args.get("sort_by", "created_at")
        sort_order = request.args.get("sort_order", "desc")

        allowed_sort_fields = ["name", "type", "standard_rate", "created_at"]
        if sort_by not in allowed_sort_fields:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_BY_MSG.format(sort_by=sort_by),
            }, 400

        if sort_order not in ["asc", "desc"]:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
            }, 400

        sort_column = getattr(ResourceModel, sort_by)
        sort_column = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        query = query.order_by(sort_column)

        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 0
        resources = query.paginate(page=page, per_page=per_page, error_out=False).items

        return cast(
            "tuple[dict, int]",
            (
                cast(
                    "dict[str, Any]",
                    self.list_schema.dump(
                        {
                            "data": resources,
                            "page": page,
                            "per_page": per_page,
                            "total": total,
                            "total_pages": total_pages,
                        }
                    ),
                ),
                200,
            ),
        )

    @require_jwt_auth
    @access_required(Operation.CREATE, "resources")
    @limiter.limit("100 per minute", key_func=_rate_limit_user_key)
    def post(self, version: str | None = None) -> tuple[dict, int]:
        """Create a new resource scoped to the authenticated company."""
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        json_payload_raw = request.get_json(silent=True)
        if json_payload_raw is None:
            json_payload: dict[str, Any] = {}
        elif isinstance(json_payload_raw, dict):
            json_payload = cast("dict[str, Any]", json_payload_raw)
        else:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        try:
            data: dict[str, Any] = cast(
                "dict[str, Any]", self.create_schema.load(json_payload)
            )
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        data["company_id"] = get_current_company_id()
        resource = ResourceModel(**data)

        try:
            db.session.add(resource)
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            error_message = str(exc.orig).lower()
            if (
                "uq_resources_company_name" in error_message
                or "resources.company_id, resources.name" in error_message
            ):
                return {
                    "error": CONFLICT_ERROR,
                    "message": DUPLICATE_RESOURCE_NAME_MSG,
                }, 409
            raise

        return cast(
            "tuple[dict, int]",
            (
                cast(
                    "dict[str, Any]",
                    self.response_schema.dump(
                        {"data": resource, "message": RESOURCE_CREATED_MSG}
                    ),
                ),
                201,
            ),
        )


class ResourceResource(Resource):
    """REST resource for single resource operations."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.resource_schema = ResourceSchema()
        self.response_schema = ResourceResponseSchema()
        self.update_schema = ResourceUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "resources")
    @limiter.limit("100 per minute", key_func=_rate_limit_user_key)
    def get(
        self,
        id: str | None = None,
        version: str | None = None,
    ) -> tuple[dict, int]:
        """Retrieve a resource by ID."""
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        if not id:
            return {"error": BAD_REQUEST_ERROR, "message": "Missing resource id"}, 400

        resource = _get_resource(id)
        if resource is None:
            return {"error": NOT_FOUND_ERROR, "message": RESOURCE_NOT_FOUND_MSG}, 404

        return cast(
            "tuple[dict, int]",
            (
                cast("dict[str, Any]", self.response_schema.dump({"data": resource})),
                200,
            ),
        )

    @require_jwt_auth
    @access_required(Operation.UPDATE, "resources")
    @limiter.limit("50 per minute", key_func=_rate_limit_user_key)
    def patch(
        self,
        id: str | None = None,
        version: str | None = None,
    ) -> tuple[dict, int]:
        """Partially update an existing resource."""
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        if not id:
            return {"error": BAD_REQUEST_ERROR, "message": "Missing resource id"}, 400

        resource = _get_resource(id)
        if resource is None:
            return {"error": NOT_FOUND_ERROR, "message": RESOURCE_NOT_FOUND_MSG}, 404

        json_payload_raw = request.get_json(silent=True)
        if json_payload_raw is not None and not isinstance(json_payload_raw, dict):
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        payload: dict[str, Any] = (
            cast("dict[str, Any]", json_payload_raw)
            if isinstance(json_payload_raw, dict)
            else {}
        )

        if not payload:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "At least one field must be provided for update",
            }, 400

        try:
            updates: dict[str, Any] = cast(
                "dict[str, Any]", self.update_schema.load(payload, partial=True)
            )
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        for field, value in updates.items():
            setattr(resource, field, value)

        try:
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            error_message = str(exc.orig)
            if "uq_resources_company_name" in error_message:
                return {
                    "error": CONFLICT_ERROR,
                    "message": DUPLICATE_RESOURCE_NAME_MSG,
                }, 409
            raise

        return cast(
            "tuple[dict, int]",
            (
                cast(
                    "dict[str, Any]",
                    self.response_schema.dump(
                        {"data": resource, "message": RESOURCE_UPDATED_MSG}
                    ),
                ),
                200,
            ),
        )

    @require_jwt_auth
    @access_required(Operation.DELETE, "resources")
    @limiter.limit("50 per minute", key_func=_rate_limit_user_key)
    def delete(
        self,
        id: str | None = None,
        version: str | None = None,
    ) -> tuple[dict, int]:
        """Delete a resource if it has no active assignments."""
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        if not id:
            return {"error": BAD_REQUEST_ERROR, "message": "Missing resource id"}, 400

        resource = _get_resource(id)
        if resource is None:
            return {"error": NOT_FOUND_ERROR, "message": RESOURCE_NOT_FOUND_MSG}, 404

        assignment_count = Assignment.query.filter(
            Assignment.resource_id == resource.id
        ).count()

        if assignment_count > 0:
            return {
                "error": CONFLICT_ERROR,
                "message": CANNOT_DELETE_WITH_ASSIGNMENTS_MSG.format(
                    count=assignment_count
                ),
            }, 409

        db.session.delete(resource)
        db.session.commit()

        return {}, 204
