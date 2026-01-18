# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Project endpoints.

Implements CRUD operations for projects with proper authentication,
authorization, validation, and pagination.
"""

import math
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.constants.http import MISSING_PROJECT_ID_MSG
from app.models.db import db
from app.models.project import Project
from app.schemas.project_schema import (
    ProjectCreateSchema,
    ProjectListResponseSchema,
    ProjectResponseSchema,
    ProjectSchema,
    ProjectUpdateSchema,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version_or_error_response
from app.utils.correlation import ResponseTuple
from app.utils.correlation import error_response as _error_response
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    require_jwt_auth,
)
from app.utils.rate_limit import rate_limit_user_key

# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"

# Error Messages
INVALID_PAGINATION_MSG = "Invalid pagination parameters"
INVALID_STATUS_MSG = "Invalid status: {status}"
INVALID_SORT_BY_MSG = "Invalid sort_by: {sort_by}"
INVALID_SORT_ORDER_MSG = "Invalid sort_order: {sort_order}"
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
PROJECT_NOT_FOUND_MSG = "Project not found"
INVALID_FINISH_DATE_MSG = "finish_date must be after start_date"
DUPLICATE_PROJECT_CODE_MSG = (
    "Project with code '{code}' already exists for this company"
)

# Success Messages
PROJECT_CREATED_MSG = "Project created successfully"
PROJECT_UPDATED_MSG = "Project updated successfully"


def _normalize_datetime(value: datetime | None) -> datetime | None:
    """Normalize datetime to naive UTC for consistent storage.

    Args:
        value: Datetime value to normalize.

    Returns:
        Naive UTC datetime or None.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _normalize_datetime_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize all datetime fields in payload to naive UTC.

    Args:
        data: Payload dictionary.

    Returns:
        Payload with normalized datetime values.
    """
    datetime_fields = [
        "start_date",
        "finish_date",
        "planned_start_date",
        "planned_finish_date",
        "creation_date",
        "last_saved_date",
    ]

    normalized = data.copy()
    for field in datetime_fields:
        if field in normalized:
            normalized[field] = _normalize_datetime(normalized[field])

    return normalized


def _parse_query_datetime(
    param_name: str, raw_value: str
) -> tuple[datetime | None, ResponseTuple | None]:
    """Parse ISO 8601 query datetime and normalize to naive UTC.

    Args:
        param_name: Name of the query parameter.
        raw_value: Raw string value.

    Returns:
        Tuple of (datetime or None, error response dict if invalid).
    """
    normalized_raw = raw_value.replace(" ", "+").replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized_raw)
    except ValueError:
        return (
            None,
            _error_response(
                f"Invalid {param_name} format. Use ISO 8601.",
                400,
                error=BAD_REQUEST_ERROR,
            ),
        )

    return _normalize_datetime(parsed), None


class ProjectListResource(Resource):
    """REST resource for project collection operations.

    Handles /v0/projects endpoint for listing and creating projects.
    """

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.project_schema = ProjectSchema()
        self.response_schema = ProjectResponseSchema()
        self.list_schema = ProjectListResponseSchema()
        self.create_schema = ProjectCreateSchema()
        self.update_schema = ProjectUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.LIST, "projects")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, version: str | None = None) -> ResponseTuple:
        """Retrieve paginated list of projects for authenticated company.

        Query Parameters:
            page (int): Page number (default: 1, min: 1)
            per_page (int): Items per page (default: 20, min: 1, max: 100)
            status (str): Filter by status (active, completed, cancelled, on_hold)
            start_date_from (datetime): Filter projects starting after this date
            start_date_to (datetime): Filter projects starting before this date
            search (str): Search in name, code, title fields
            sort_by (str): Field to sort by (name, code, start_date, created_at)
            sort_order (str): Sort direction (asc, desc)

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Successful response with paginated project list
                - 400: Invalid query parameters
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions

        Examples:
            >>> GET /v0/projects?page=1&per_page=20&status=active
            {
                "data": [...],
                "page": 1,
                "per_page": 20,
                "total": 150,
                "total_pages": 8
            }
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id = get_current_company_id()

        # Parse and validate pagination parameters
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return _error_response(INVALID_PAGINATION_MSG, 400, error=BAD_REQUEST_ERROR)

        # Build base query filtered by company
        query = Project.query.filter_by(company_id=company_id)

        # Apply status filter
        status = request.args.get("status")
        if status:
            if status not in [
                "initialized",
                "active",
                "completed",
                "cancelled",
                "on_hold",
            ]:
                return _error_response(
                    INVALID_STATUS_MSG.format(status=status),
                    400,
                    error=BAD_REQUEST_ERROR,
                )
            query = query.filter_by(status=status)

        # Apply date range filters
        start_date_from = request.args.get("start_date_from")
        if start_date_from:
            start_date_from_dt, error = _parse_query_datetime(
                "start_date_from", start_date_from
            )
            if error:
                return error
            query = query.filter(Project.start_date >= start_date_from_dt)

        start_date_to = request.args.get("start_date_to")
        if start_date_to:
            start_date_to_dt, error = _parse_query_datetime(
                "start_date_to", start_date_to
            )
            if error:
                return error
            query = query.filter(Project.start_date <= start_date_to_dt)

        # Apply search filter (name, code, title)
        # Note: title is nullable, so we use coalesce to handle NULL values
        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Project.name.ilike(search_pattern),
                    Project.code.ilike(search_pattern),
                    func.coalesce(Project.title, "").ilike(search_pattern),
                )
            )

        # Apply sorting
        sort_by = request.args.get("sort_by", "created_at")
        sort_order = request.args.get("sort_order", "desc")

        if sort_by not in ["name", "code", "start_date", "created_at"]:
            return _error_response(
                INVALID_SORT_BY_MSG.format(sort_by=sort_by),
                400,
                error=BAD_REQUEST_ERROR,
            )

        if sort_order not in ["asc", "desc"]:
            return _error_response(
                INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
                400,
                error=BAD_REQUEST_ERROR,
            )

        # Get sortable column
        sort_column = getattr(Project, sort_by)
        sort_column = sort_column.desc() if sort_order == "desc" else sort_column.asc()

        query = query.order_by(sort_column)

        # Get total count before pagination
        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 0

        # Apply pagination
        projects = query.paginate(page=page, per_page=per_page, error_out=False).items

        # Serialize response
        result = cast(
            "dict[str, Any]",
            self.list_schema.dump(
                {
                    "data": projects,
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                }
            ),
        )
        return result, 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "projects")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def post(self, version: str | None = None) -> ResponseTuple:
        """Create a new project for the authenticated company.

        Request Body:
            JSON object validated by ProjectCreateSchema:
                - name (str, required): Project name (max 255 chars)
                - code (str, required): Project code (max 50 chars, unique per company)
                - title (str, optional): Project title (max 255 chars)
                - start_date (datetime, required): Project start date
                - finish_date (datetime, required): Project finish date (must be after start_date)
                - status (str, optional): Project status (initialized, active, completed, cancelled, on_hold, default: initialized)
                - budget (decimal, optional): Project budget (max 18 digits, 2 decimals)
                - description (str, optional): Project description (max 2000 chars)
                - MS Project fields (optional): Various UIDs, GUIDs, calendar settings

        Returns:
            Tuple of (response_dict, status_code):
                - 201: Project created successfully
                - 400: Validation failed (invalid data format)
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions (missing CREATE permission)
                - 409: Conflict (duplicate project code for company)
                - 422: Business rule violation (finish_date before start_date)

        Examples:
            Request:
            >>> POST /v0/projects
            {
                "name": "New Project",
                "code": "PROJ-001",
                "start_date": "2026-01-01T09:00:00Z",
                "finish_date": "2026-12-31T18:00:00Z",
                "status": "active",
                "budget": 100000.00
            }

            Success Response (201):
            {
                "data": {
                    "id": "uuid",
                    "name": "New Project",
                    "code": "PROJ-001",
                    ...
                },
                "message": "Project created successfully"
            }
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

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
                error=BAD_REQUEST_ERROR,
                errors=err.messages,
            )

        normalized = _normalize_datetime_fields(data)
        normalized["company_id"] = get_current_company_id()
        # Validate business rule: finish_date must be after start_date
        start_date = normalized.get("start_date")
        finish_date = normalized.get("finish_date")
        if start_date and finish_date and finish_date <= start_date:
            return _error_response(
                INVALID_FINISH_DATE_MSG, 422, error="Unprocessable Entity"
            )
        project = Project(**normalized)

        try:
            db.session.add(project)
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            error_message = str(exc.orig)
            if (
                "uq_projects_company_code" in error_message
                or "projects.company_id, projects.code" in error_message
            ):
                return _error_response(
                    DUPLICATE_PROJECT_CODE_MSG.format(code=normalized.get("code")),
                    409,
                    error=CONFLICT_ERROR,
                )
            raise

        return cast(
            "dict[str, Any]",
            self.response_schema.dump(
                {"data": project, "message": PROJECT_CREATED_MSG}
            ),
        ), 201


class ProjectResource(Resource):
    """REST resource for individual project operations."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.project_schema = ProjectSchema()
        self.response_schema = ProjectResponseSchema()
        self.update_schema = ProjectUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "projects")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self,
        project_id: str | None = None,
        id: str | None = None,
        version: str | None = None,
    ) -> ResponseTuple:
        """Retrieve a single project by ID.

        Path Parameters:
            project_id (str): UUID of the project to retrieve

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Project found and returned successfully
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions (missing READ permission)
                - 404: Project not found or not accessible (wrong company)

        Examples:
            Request:
            >>> GET /v0/projects/{uuid}

            Success Response (200):
            {
                "data": {
                    "id": "uuid",
                    "name": "Project Name",
                    "code": "PROJ-001",
                    "start_date": "2026-01-01T09:00:00Z",
                    "finish_date": "2026-12-31T18:00:00Z",
                    ...
                }
            }
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        effective_id = project_id or id
        if not effective_id:
            return _error_response(MISSING_PROJECT_ID_MSG, 400, error=BAD_REQUEST_ERROR)

        project = self._get_project(effective_id)
        if project is None:
            return _error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

        return cast("dict[str, Any]", self.response_schema.dump({"data": project})), 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "projects")
    @limiter.limit("50 per minute", key_func=rate_limit_user_key)
    def patch(
        self,
        project_id: str | None = None,
        id: str | None = None,
        version: str | None = None,
    ) -> ResponseTuple:
        """Partially update a project.

        Path Parameters:
            project_id (str): UUID of the project to update

        Request Body:
            JSON object with fields to update (all optional):
                - name (str): Project name (max 255 chars)
                - code (str): Project code (max 50 chars, unique per company)
                - title (str): Project title (max 255 chars)
                - start_date (datetime): Project start date
                - finish_date (datetime): Project finish date (must be after start_date)
                - status (str): Project status (initialized, active, completed, cancelled, on_hold)
                - budget (decimal): Project budget (max 18 digits, 2 decimals)
                - description (str): Project description (max 2000 chars)
                - MS Project fields: Various UIDs, GUIDs, calendar settings

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Project updated successfully
                - 400: Validation failed (invalid data or finish_date before start_date)
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions (missing UPDATE permission)
                - 404: Project not found or not accessible (wrong company)
                - 409: Conflict (duplicate project code for company)

        Examples:
            Request:
            >>> PATCH /v0/projects/{uuid}
            {
                "name": "Updated Name",
                "status": "completed"
            }

            Success Response (200):
            {
                "data": {
                    "id": "uuid",
                    "name": "Updated Name",
                    "status": "completed",
                    ...
                },
                "message": "Project updated successfully"
            }
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        effective_id = project_id or id
        if not effective_id:
            return _error_response(MISSING_PROJECT_ID_MSG, 400, error=BAD_REQUEST_ERROR)

        project = self._get_project(effective_id)
        if project is None:
            return _error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

        json_payload_raw = request.get_json(silent=True)
        if json_payload_raw is not None and not isinstance(json_payload_raw, dict):
            return _error_response(
                "Request body must be a JSON object",
                400,
                error=BAD_REQUEST_ERROR,
            )

        payload: dict[str, Any] = (
            cast("dict[str, Any]", json_payload_raw)
            if isinstance(json_payload_raw, dict)
            else {}
        )

        # Validate minProperties: 1 (OpenAPI requirement)
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
                error=BAD_REQUEST_ERROR,
                errors=err.messages,
            )

        normalized = _normalize_datetime_fields(updates)

        new_start = normalized.get("start_date", project.start_date)
        new_finish = normalized.get("finish_date", project.finish_date)
        if new_start and new_finish and new_finish <= new_start:
            return _error_response(
                INVALID_FINISH_DATE_MSG, 422, error="Unprocessable Entity"
            )

        for field, value in normalized.items():
            setattr(project, field, value)

        try:
            db.session.commit()
        except IntegrityError as exc:  # pragma: no cover - guarded by tests
            db.session.rollback()
            error_message = str(exc.orig)
            if (
                "uq_projects_company_code" in error_message
                or "projects.company_id, projects.code" in error_message
            ):
                return _error_response(
                    DUPLICATE_PROJECT_CODE_MSG.format(code=normalized.get("code")),
                    409,
                    error=CONFLICT_ERROR,
                )
            raise

        return cast(
            "dict[str, Any]",
            self.response_schema.dump(
                {"data": project, "message": PROJECT_UPDATED_MSG}
            ),
        ), 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "projects")
    @limiter.limit("50 per minute", key_func=rate_limit_user_key)
    def delete(
        self,
        project_id: str | None = None,
        id: str | None = None,
        version: str | None = None,
    ) -> ResponseTuple:
        """Delete a project if no related entities exist.

        Path Parameters:
            project_id (str): UUID of the project to delete

        Returns:
            Tuple of (response_dict, status_code):
                - 204: Project deleted successfully (no content)
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions (missing DELETE permission)
                - 404: Project not found or not accessible (wrong company)
                - 409: Conflict (project has related tasks, assignments, milestones, or EVM snapshots)
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        effective_id = project_id or id
        if not effective_id:
            return _error_response(MISSING_PROJECT_ID_MSG, 400, error=BAD_REQUEST_ERROR)

        project = self._get_project(effective_id)
        if project is None:
            return _error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

        has_related = any(
            [
                project.tasks,
                project.milestones,
                project.expenses,
                project.assignments,
                project.progress_updates,
                project.evm_snapshots,
            ]
        )

        if has_related:
            return _error_response(
                "Cannot delete project with existing tasks/milestones/expenses/assignments",
                409,
                error=CONFLICT_ERROR,
            )

        db.session.delete(project)
        db.session.commit()

        return "", 204

    @staticmethod
    def _get_project(project_id: str) -> Project | None:
        """Load a project for the current company.

        Args:
            project_id: Project UUID string.

        Returns:
            Project instance or None if not found/invalid.
        """
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return None

        company_id = get_current_company_id()
        return Project.query.filter_by(id=project_uuid, company_id=company_id).first()
