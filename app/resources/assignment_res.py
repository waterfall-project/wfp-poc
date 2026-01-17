# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Assignment endpoints.

Implements CRUD operations for task-resource assignments with authentication,
authorization, validation, and pagination according to the OpenAPI contract.
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import Any

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.constants.http import (
    BAD_REQUEST_ERROR,
    CONFLICT_ERROR,
    INVALID_ASSIGNMENT_ID_MSG,
    INVALID_JSON_BODY_MSG,
    INVALID_PAGINATION_MSG,
    INVALID_PROJECT_ID_MSG,
    INVALID_RESOURCE_ID_MSG,
    INVALID_TASK_ID_MSG,
    NOT_FOUND_ERROR,
    UNPROCESSABLE_ENTITY_ERROR,
    VALIDATION_FAILED_MSG,
)
from app.models.assignment import Assignment
from app.models.db import db
from app.models.project import Project
from app.models.resource import Resource as ResourceModel
from app.models.task import Task
from app.schemas.assignment_schema import (
    AssignmentCreateSchema,
    AssignmentListResponseSchema,
    AssignmentResponseSchema,
    AssignmentSchema,
    AssignmentUpdateSchema,
    _duration_to_minutes,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version_or_error_response
from app.utils.correlation import ResponseTuple
from app.utils.correlation import error_response as _error_response
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_uuid,
    require_jwt_auth,
)
from app.utils.rate_limit import rate_limit_user_key

# Error Messages
PROJECT_NOT_FOUND_MSG = "Project not found"
ASSIGNMENT_NOT_FOUND_MSG = "Assignment not found"
TASK_OR_RESOURCE_NOT_FOUND_MSG = "Task or resource not found"
CROSS_COMPANY_MSG = "Resource and task must belong to the same company"
DUPLICATE_ASSIGNMENT_MSG = "Assignment already exists for this task and resource"
USER_CONTEXT_MISSING_MSG = "User context missing. Use @require_jwt_auth first."

# Success Messages
ASSIGNMENT_CREATED_MSG = "Assignment created successfully"
ASSIGNMENT_UPDATED_MSG = "Assignment updated successfully"


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a string into UUID, returning None when invalid."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _get_project_scoped(
    project_id: uuid.UUID, company_id: uuid.UUID | None
) -> Project | None:
    """Retrieve project scoped to current company."""
    if not company_id:
        return None
    return Project.query.filter_by(id=project_id, company_id=company_id).first()


def _get_task_scoped(task_id: str, project_id: uuid.UUID) -> Task | None:
    """Retrieve task scoped to project."""
    task_uuid = _parse_uuid(task_id)
    if not task_uuid:
        return None
    return Task.query.filter_by(id=task_uuid, project_id=project_id).first()


def _get_resource_scoped(
    resource_id: str, company_id: uuid.UUID | None
) -> ResourceModel | None:
    """Retrieve resource scoped to company."""
    resource_uuid = _parse_uuid(resource_id)
    if not resource_uuid or not company_id:
        return None
    return ResourceModel.query.filter_by(
        id=resource_uuid, company_id=company_id
    ).first()


def _get_json_object_or_error() -> tuple[dict[str, Any], ResponseTuple | None]:
    """Return JSON payload as dict or an error response when invalid."""
    json_payload_raw = request.get_json(silent=True)
    if json_payload_raw is None:
        return {}, None
    if isinstance(json_payload_raw, dict):
        return json_payload_raw, None
    return {}, _error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)


def _get_resource_any_company(resource_id: uuid.UUID) -> ResourceModel | None:
    """Retrieve resource without company scoping for cross-company validation."""
    return ResourceModel.query.filter_by(id=resource_id).first()


def _get_assignment_scoped(
    assignment_id: uuid.UUID, project_id: uuid.UUID
) -> Assignment | None:
    """Retrieve assignment scoped to project."""
    return Assignment.query.filter_by(id=assignment_id, project_id=project_id).first()


def _get_company_id_or_error() -> tuple[uuid.UUID | None, ResponseTuple | None]:
    """Return company UUID or an unauthorized error response."""
    company_id = get_current_company_uuid()
    if not company_id:
        return None, _error_response(
            USER_CONTEXT_MISSING_MSG, 401, error="Unauthorized"
        )
    return company_id, None


def _get_project_or_error(
    project_id: str, company_id: uuid.UUID
) -> tuple[Project | None, ResponseTuple | None]:
    """Return project or an error response for invalid/missing project."""
    project_uuid = _parse_uuid(project_id)
    if not project_uuid:
        return None, _error_response(
            INVALID_PROJECT_ID_MSG, 400, error=BAD_REQUEST_ERROR
        )

    project = _get_project_scoped(project_uuid, company_id)
    if not project:
        return None, _error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

    return project, None


def _get_assignment_or_error(
    project: Project, assignment_id: str
) -> tuple[Assignment | None, ResponseTuple | None]:
    """Return assignment or an error response for invalid/missing assignment."""
    assignment_uuid = _parse_uuid(assignment_id)
    if not assignment_uuid:
        return None, _error_response(
            INVALID_ASSIGNMENT_ID_MSG, 400, error=BAD_REQUEST_ERROR
        )

    assignment = _get_assignment_scoped(assignment_uuid, project.id)
    if not assignment:
        return None, _error_response(
            ASSIGNMENT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR
        )

    return assignment, None


def _get_task_and_resource_or_error(
    data: dict[str, Any],
    project: Project,
    company_id: uuid.UUID,
) -> tuple[Task | None, ResourceModel | None, ResponseTuple | None]:
    """Return task/resource or a validation error response."""
    task = _get_task_scoped(str(data["task_id"]), project.id)
    resource = _get_resource_scoped(str(data["resource_id"]), company_id)

    if not task:
        return (
            None,
            None,
            _error_response(TASK_OR_RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR),
        )

    resource_uuid = _parse_uuid(str(data["resource_id"]))
    if not resource and resource_uuid:
        resource_any = _get_resource_any_company(resource_uuid)
        if resource_any:
            return (
                None,
                None,
                _error_response(
                    CROSS_COMPANY_MSG, 422, error=UNPROCESSABLE_ENTITY_ERROR
                ),
            )
        return (
            None,
            None,
            _error_response(TASK_OR_RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR),
        )

    if not resource:
        return (
            None,
            None,
            _error_response(TASK_OR_RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR),
        )

    if project.company_id != resource.company_id:
        return (
            None,
            None,
            _error_response(CROSS_COMPANY_MSG, 422, error=UNPROCESSABLE_ENTITY_ERROR),
        )

    return task, resource, None


def _normalize_ms_project_uid(value: Any) -> int | None:
    """Normalize MS Project UID to int or None after schema validation."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _normalize_cost_decimal(value: Any) -> Decimal | None:
    """Normalize cost inputs to Decimal or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (float, int)):
        return Decimal(str(value))
    return None


def _apply_assignment_updates(assignment: Assignment, data: dict[str, Any]) -> None:
    """Apply partial update payload to an assignment instance."""
    if "work_hours" in data:
        assignment.planned_work_minutes = _duration_to_minutes(data["work_hours"])
    if "percent_allocation" in data:
        assignment.percent_allocation = data["percent_allocation"]
    if "cost" in data:
        assignment.planned_cost = _normalize_cost_decimal(data["cost"])
    if "actual_work" in data:
        assignment.actual_work_minutes = _duration_to_minutes(data["actual_work"])
    if "actual_cost" in data:
        normalized_actual_cost = _normalize_cost_decimal(data["actual_cost"])
        if normalized_actual_cost is not None:
            assignment.actual_cost = normalized_actual_cost


class AssignmentListResource(Resource):
    """REST resource for collection operations on assignments."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.assignment_schema = AssignmentSchema()
        self.response_schema = AssignmentResponseSchema()
        self.list_schema = AssignmentListResponseSchema()
        self.create_schema = AssignmentCreateSchema()
        self.update_schema = AssignmentUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.LIST, "assignments")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """List assignments for a project with pagination and filters."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_id_or_error()
        if company_error:
            return company_error

        assert company_id is not None
        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None

        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return _error_response(INVALID_PAGINATION_MSG, 400, error=BAD_REQUEST_ERROR)

        query = Assignment.query.filter_by(project_id=project.id)

        task_filter = request.args.get("task_id")
        if task_filter:
            task_uuid = _parse_uuid(task_filter)
            if not task_uuid:
                return _error_response(
                    INVALID_TASK_ID_MSG, 400, error=BAD_REQUEST_ERROR
                )
            query = query.filter(Assignment.task_id == task_uuid)

        resource_filter = request.args.get("resource_id")
        if resource_filter:
            resource_uuid = _parse_uuid(resource_filter)
            if not resource_uuid:
                return _error_response(
                    INVALID_RESOURCE_ID_MSG, 400, error=BAD_REQUEST_ERROR
                )
            query = query.filter(Assignment.resource_id == resource_uuid)

        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 0

        assignments = (
            query.order_by(Assignment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        data = self.list_schema.dump(
            {
                "data": assignments,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            }
        )

        return data, 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "assignments")
    @limiter.limit("20 per minute", key_func=rate_limit_user_key)
    def post(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Create a new assignment."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_id_or_error()
        if company_error:
            return company_error

        assert company_id is not None
        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None

        payload, json_error = _get_json_object_or_error()
        if json_error:
            return json_error

        try:
            loaded = self.create_schema.load(payload)
        except ValidationError as err:
            return _error_response(
                VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR, errors=err.messages
            )

        if not isinstance(loaded, dict):
            return _error_response(VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR)

        data: dict[str, Any] = loaded

        task, resource, resource_error = _get_task_and_resource_or_error(
            data, project, company_id
        )
        if resource_error:
            return resource_error

        assert task is not None
        assert resource is not None

        existing = Assignment.query.filter_by(
            task_id=task.id, resource_id=resource.id
        ).first()
        if existing:
            return _error_response(DUPLICATE_ASSIGNMENT_MSG, 409, error=CONFLICT_ERROR)

        planned_work_minutes = _duration_to_minutes(data.get("work_hours"))
        cost = data.get("cost")
        planned_cost = _normalize_cost_decimal(cost)

        ms_project_uid = _normalize_ms_project_uid(data.get("ms_project_uid"))

        assignment = Assignment(
            project_id=project.id,
            task_id=task.id,
            resource_id=resource.id,
            ms_project_uid=ms_project_uid,
            percent_allocation=data.get("percent_allocation", 100),
            planned_work_minutes=planned_work_minutes,
            planned_cost=planned_cost,
            actual_cost=0,
        )

        try:
            db.session.add(assignment)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return _error_response(DUPLICATE_ASSIGNMENT_MSG, 409, error=CONFLICT_ERROR)

        response_data = self.response_schema.dump(
            {
                "data": assignment,
                "message": ASSIGNMENT_CREATED_MSG,
            }
        )
        return response_data, 201


class AssignmentResource(Resource):
    """REST resource for item operations on assignments."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.assignment_schema = AssignmentSchema()
        self.response_schema = AssignmentResponseSchema()
        self.update_schema = AssignmentUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "assignments")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Retrieve a single assignment by ID."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_id_or_error()
        if company_error:
            return company_error

        assert company_id is not None
        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None
        assignment, assignment_error = _get_assignment_or_error(project, id)
        if assignment_error:
            return assignment_error

        assert assignment is not None

        response_data = self.response_schema.dump({"data": assignment})
        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "assignments")
    @limiter.limit("60 per minute", key_func=rate_limit_user_key)
    def patch(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Partially update an assignment."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_id_or_error()
        if company_error:
            return company_error

        assert company_id is not None
        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None
        assignment, assignment_error = _get_assignment_or_error(project, id)
        if assignment_error:
            return assignment_error

        assert assignment is not None

        payload, json_error = _get_json_object_or_error()
        if json_error:
            return json_error

        try:
            loaded = self.update_schema.load(payload)
        except ValidationError as err:
            return _error_response(
                VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR, errors=err.messages
            )

        if not isinstance(loaded, dict):
            return _error_response(VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR)

        data: dict[str, Any] = loaded

        _apply_assignment_updates(assignment, data)

        db.session.commit()

        response_data = self.response_schema.dump(
            {"data": assignment, "message": ASSIGNMENT_UPDATED_MSG}
        )
        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "assignments")
    @limiter.limit("30 per minute", key_func=rate_limit_user_key)
    def delete(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Delete an assignment."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_id_or_error()
        if company_error:
            return company_error

        assert company_id is not None
        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None
        assignment, assignment_error = _get_assignment_or_error(project, id)
        if assignment_error:
            return assignment_error

        assert assignment is not None

        db.session.delete(assignment)
        db.session.commit()
        return "", 204
