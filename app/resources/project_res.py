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
from typing import Any

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import limiter
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
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    get_current_user_id,
    require_jwt_auth,
)


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
) -> tuple[datetime | None, dict | None]:
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
        return None, {
            "error": "Bad Request",
            "message": f"Invalid {param_name} format. Use ISO 8601.",
        }

    return _normalize_datetime(parsed), None


def _rate_limit_user_key() -> str:
    """Rate limiting key based on authenticated user.

    Falls back to remote address when user_id is absent.
    """
    user_id = get_current_user_id()
    if user_id:
        return str(user_id)
    return request.remote_addr or "anonymous"


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
    @limiter.limit("100 per minute", key_func=_rate_limit_user_key)
    def get(self) -> tuple[dict, int]:
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
        company_id = get_current_company_id()

        # Parse and validate pagination parameters
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return {
                "error": "Bad Request",
                "message": "Invalid pagination parameters",
            }, 400

        # Build base query filtered by company
        query = Project.query.filter_by(company_id=company_id)

        # Apply status filter
        status = request.args.get("status")
        if status:
            if status not in ["active", "completed", "cancelled", "on_hold"]:
                return {
                    "error": "Bad Request",
                    "message": f"Invalid status: {status}",
                }, 400
            query = query.filter_by(status=status)

        # Apply date range filters
        start_date_from = request.args.get("start_date_from")
        if start_date_from:
            start_date_from_dt, error = _parse_query_datetime(
                "start_date_from", start_date_from
            )
            if error:
                return error, 400
            query = query.filter(Project.start_date >= start_date_from_dt)

        start_date_to = request.args.get("start_date_to")
        if start_date_to:
            start_date_to_dt, error = _parse_query_datetime(
                "start_date_to", start_date_to
            )
            if error:
                return error, 400
            query = query.filter(Project.start_date <= start_date_to_dt)

        # Apply search filter (name, code, title)
        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Project.name.ilike(search_pattern),
                    Project.code.ilike(search_pattern),
                    Project.title.ilike(search_pattern),
                )
            )

        # Apply sorting
        sort_by = request.args.get("sort_by", "created_at")
        sort_order = request.args.get("sort_order", "desc")

        if sort_by not in ["name", "code", "start_date", "created_at"]:
            return {
                "error": "Bad Request",
                "message": f"Invalid sort_by: {sort_by}",
            }, 400

        if sort_order not in ["asc", "desc"]:
            return {
                "error": "Bad Request",
                "message": f"Invalid sort_order: {sort_order}",
            }, 400

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
        return self.list_schema.dump(
            {
                "data": projects,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            }
        ), 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "projects")
    def post(self) -> tuple[dict, int]:
        """Create a new project for the authenticated company.

        Returns:
            Tuple of serialized project and status code.
        """
        json_payload = request.get_json() or {}

        try:
            data = self.create_schema.load(json_payload)
        except ValidationError as err:
            return {
                "error": "Bad Request",
                "message": "Validation failed",
                "errors": err.messages,
            }, 400

        normalized = _normalize_datetime_fields(data)
        normalized["company_id"] = get_current_company_id()

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
                return {
                    "error": "Conflict",
                    "message": f"Project with code '{normalized.get('code')}' already exists for this company",
                }, 409
            raise

        return self.response_schema.dump(
            {"data": project, "message": "Project created successfully"}
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
    def get(self, project_id: str) -> tuple[dict, int]:
        """Retrieve a single project by ID."""
        project = self._get_project(project_id)
        if project is None:
            return {"error": "Not Found", "message": "Project not found"}, 404

        return self.response_schema.dump({"data": project}), 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "projects")
    def patch(self, project_id: str) -> tuple[dict, int]:
        """Partially update a project."""
        project = self._get_project(project_id)
        if project is None:
            return {"error": "Not Found", "message": "Project not found"}, 404

        json_payload = request.get_json() or {}

        try:
            updates = self.update_schema.load(json_payload, partial=True)
        except ValidationError as err:
            return {
                "error": "Bad Request",
                "message": "Validation failed",
                "errors": err.messages,
            }, 400

        normalized = _normalize_datetime_fields(updates)

        new_start = normalized.get("start_date", project.start_date)
        new_finish = normalized.get("finish_date", project.finish_date)
        if new_start and new_finish and new_finish <= new_start:
            return {
                "error": "Bad Request",
                "message": "finish_date must be after start_date",
            }, 400

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
                return {
                    "error": "Conflict",
                    "message": f"Project with code '{normalized.get('code')}' already exists for this company",
                }, 409
            raise

        return self.response_schema.dump(
            {"data": project, "message": "Project updated successfully"}
        ), 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "projects")
    def delete(self, project_id: str) -> tuple[dict, int]:
        """Delete a project if it has no related entities."""
        project = self._get_project(project_id)
        if project is None:
            return {"error": "Not Found", "message": "Project not found"}, 404

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
            return {
                "error": "Conflict",
                "message": "Cannot delete project with existing tasks/milestones/expenses/assignments",
            }, 409

        db.session.delete(project)
        db.session.commit()

        return {}, 204

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
