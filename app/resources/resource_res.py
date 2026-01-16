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
from app.utils.correlation import error_response as _error_response
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

# Typing helper for Flask-style responses (body, status[, headers])
ResponseTuple = tuple[Any, int] | tuple[Any, int, dict[str, str]]

# Allowed sort fields for resource listing
ALLOWED_SORT_FIELDS = ["name", "type", "email", "standard_rate", "overtime_rate", "created_at", "updated_at"]


def _rate_limit_user_key() -> str:
    """Rate limiting key based on authenticated user."""
    user_id = get_current_user_id()
    if user_id:
        return str(user_id)
    return request.remote_addr or "anonymous"


def _parse_bool_param(value: str | None) -> tuple[bool | None, str | None]:
    """Parse boolean-like query parameter values."""
    if value is None:
        return None, None

    normalized = value.strip().lower()
    if normalized in ["true", "1", "yes"]:
        return True, None
    if normalized in ["false", "0", "no"]:
        return False, None

    return None, INVALID_IS_ACTIVE_MSG.format(value=value)


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
    def get(self, version: str | None = None) -> ResponseTuple:
        """List resources for the authenticated company with pagination."""
        version_error = validate_api_version(version)
        if version_error:
            return _error_response(
                version_error[0].get("message", "Unsupported API version"),
                version_error[1],
                error=version_error[0].get("error"),
            )

        company_id = get_current_company_id()

        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return _error_response(INVALID_PAGINATION_MSG, 400, error=BAD_REQUEST_ERROR)

        query = ResourceModel.query.filter_by(company_id=company_id)

        resource_type = request.args.get("type")
        if resource_type:
            if resource_type not in ["labor", "material", "cost"]:
                return _error_response(
                    INVALID_TYPE_MSG.format(resource_type=resource_type),
                    400,
                    error=BAD_REQUEST_ERROR,
                )
            query = query.filter(ResourceModel.type == resource_type)

        is_active_param = request.args.get("is_active")
        is_active, error_message = _parse_bool_param(is_active_param)
        if error_message:
            return _error_response(error_message, 400, error=BAD_REQUEST_ERROR)
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

        if sort_order not in ["asc", "desc"]:
            return _error_response(
                INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
                400,
                error=BAD_REQUEST_ERROR,
            )

        # Validate sort_by against whitelist, fall back to created_at if invalid
        # This provides permissive handling - invalid values gracefully degrade
        # to default sort rather than returning an error
        if sort_by not in ALLOWED_SORT_FIELDS:
            sort_by = "created_at"

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
    def post(self, version: str | None = None) -> ResponseTuple:
        """Create a new resource scoped to the authenticated company."""
        version_error = validate_api_version(version)
        if version_error:
            return _error_response(
                version_error[0].get("message", "Unsupported API version"),
                version_error[1],
                error=version_error[0].get("error"),
            )

        json_payload_raw = request.get_json(silent=True)
        if json_payload_raw is None:
            json_payload: dict[str, Any] = {}
        elif isinstance(json_payload_raw, dict):
            json_payload = cast("dict[str, Any]", json_payload_raw)
        else:
            return _error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        try:
            data: dict[str, Any] = cast(
                "dict[str, Any]", self.create_schema.load(json_payload)
            )
        except ValidationError as err:
            return _error_response(
                VALIDATION_FAILED_MSG,
                400,
                errors=err.messages,
                error=BAD_REQUEST_ERROR,
            )

        data["company_id"] = get_current_company_id()
        resource = ResourceModel(**data)

        try:
            db.session.add(resource)
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            # Check for unique constraint violation on (company_id, name)
            # This is more robust than string matching on error messages
            constraint_name = getattr(exc.orig, "constraint_name", None)
            if constraint_name == "uq_resources_company_name":
                return _error_response(
                    DUPLICATE_RESOURCE_NAME_MSG, 409, error=CONFLICT_ERROR
                )
            # Fallback: check error message for database-specific constraint indicators
            error_message = str(exc.orig).lower()
            if "uq_resources_company_name" in error_message or (
                "unique" in error_message
                and "company_id" in error_message
                and "name" in error_message
            ):
                return _error_response(
                    DUPLICATE_RESOURCE_NAME_MSG, 409, error=CONFLICT_ERROR
                )
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
    ) -> ResponseTuple:
        """Retrieve a resource by ID."""
        version_error = validate_api_version(version)
        if version_error:
            return _error_response(
                version_error[0].get("message", "Unsupported API version"),
                version_error[1],
                error=version_error[0].get("error"),
            )

        if not id:
            return _error_response("Missing resource id", 400, error=BAD_REQUEST_ERROR)

        resource = _get_resource(id)
        if resource is None:
            return _error_response(RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

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
    ) -> ResponseTuple:
        """Partially update an existing resource."""
        version_error = validate_api_version(version)
        if version_error:
            return _error_response(
                version_error[0].get("message", "Unsupported API version"),
                version_error[1],
                error=version_error[0].get("error"),
            )

        if not id:
            return _error_response("Missing resource id", 400, error=BAD_REQUEST_ERROR)

        resource = _get_resource(id)
        if resource is None:
            return _error_response(RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

        json_payload_raw = request.get_json(silent=True)
        if json_payload_raw is not None and not isinstance(json_payload_raw, dict):
            return _error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        payload: dict[str, Any] = (
            cast("dict[str, Any]", json_payload_raw)
            if isinstance(json_payload_raw, dict)
            else {}
        )

        if not payload:
            return _error_response(
                "At least one field must be provided for update",
                400,
                error=BAD_REQUEST_ERROR,
            )

        try:
            updates: dict[str, Any] = cast(
                "dict[str, Any]", self.update_schema.load(payload, partial=True)
            )
        except ValidationError as err:
            return _error_response(
                VALIDATION_FAILED_MSG,
                400,
                errors=err.messages,
                error=BAD_REQUEST_ERROR,
            )

        for field, value in updates.items():
            setattr(resource, field, value)

        try:
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            # Check for unique constraint violation on (company_id, name)
            # This is more robust than string matching on error messages
            constraint_name = getattr(exc.orig, "constraint_name", None)
            if constraint_name == "uq_resources_company_name":
                return _error_response(
                    DUPLICATE_RESOURCE_NAME_MSG, 409, error=CONFLICT_ERROR
                )
            # Fallback: check error message for database-specific constraint indicators
            error_message = str(exc.orig).lower()
            if "uq_resources_company_name" in error_message or (
                "unique" in error_message
                and "company_id" in error_message
                and "name" in error_message
            ):
                return _error_response(
                    DUPLICATE_RESOURCE_NAME_MSG, 409, error=CONFLICT_ERROR
                )
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
    ) -> ResponseTuple:
        """Delete a resource if it has no active assignments."""
        version_error = validate_api_version(version)
        if version_error:
            return _error_response(
                version_error[0].get("message", "Unsupported API version"),
                version_error[1],
                error=version_error[0].get("error"),
            )

        if not id:
            return _error_response("Missing resource id", 400, error=BAD_REQUEST_ERROR)

        resource = _get_resource(id)
        if resource is None:
            return _error_response(RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

        assignment_count = Assignment.query.filter(
            Assignment.resource_id == resource.id
        ).count()

        if assignment_count > 0:
            return _error_response(
                CANNOT_DELETE_WITH_ASSIGNMENTS_MSG.format(count=assignment_count),
                409,
                error=CONFLICT_ERROR,
            )

        db.session.delete(resource)
        db.session.commit()

        return "", 204
