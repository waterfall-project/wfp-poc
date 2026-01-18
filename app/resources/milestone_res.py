# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Milestone endpoints.

Implements CRUD operations for milestones with proper authentication,
authorization, validation, and budget_weight constraints.
"""

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.db import db
from app.models.milestone import Milestone
from app.models.project import Project
from app.schemas.milestone_schema import (
    MilestoneCreateSchema,
    MilestoneSchema,
    MilestoneUpdateSchema,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version_or_error_response
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
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"
INVALID_PROJECT_OR_MILESTONE_ID_MSG = "Invalid project_id or milestone id"

ErrorResponse = tuple[dict[str, Any], int]

# Error Messages
INVALID_PAGINATION_MSG = "Invalid pagination parameters"
INVALID_STATUS_MSG = "Invalid status: {status}"
INVALID_SORT_BY_MSG = "Invalid sort_by: {sort_by}"
INVALID_SORT_ORDER_MSG = "Invalid sort_order: {sort_order}"
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
MILESTONE_NOT_FOUND_MSG = "Milestone not found"
PROJECT_NOT_FOUND_MSG = "Project not found"
BUDGET_WEIGHT_SUM_EXCEEDED_MSG = "Sum of milestone budget_weight would exceed 1.0 (current: {current}, adding: {adding})"
CANNOT_DELETE_MILESTONE_WITH_EXPENSES_MSG = (
    "Cannot delete milestone with {count} associated expenses"
)
INVALID_TARGET_DATE_RANGE_MSG = "target_date must fall within project date range"
INVALID_ACTUAL_DATE_RANGE_MSG = "actual_date must fall within project date range"
MILESTONE_OVERLAP_MSG = "milestones must not overlap"
INVALID_COMPANY_ID_CLAIM_MSG = "Invalid token: company_id claim is not a valid UUID."

# Success Messages
MILESTONE_CREATED_MSG = "Milestone created successfully"
MILESTONE_UPDATED_MSG = "Milestone updated successfully"


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
    datetime_fields = ["target_date", "actual_date", "achieved_date"]

    for field in datetime_fields:
        if field in data and data[field] is not None:
            data[field] = _normalize_datetime(data[field])

    return data


def _derive_milestone_status(
    target_date: datetime | None, actual_date: datetime | None
) -> str:
    """Derive milestone status from target and actual dates.

    Args:
        target_date: Planned milestone completion date.
        actual_date: Actual milestone completion date.

    Returns:
        Milestone status: upcoming, achieved, or missed.
    """
    if actual_date is None:
        return "upcoming"
    if target_date and actual_date > target_date:
        return "missed"
    return "achieved"


def _prepare_milestone_update_data(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Normalize milestone update payload for achieved status logic.

    Args:
        data: Incoming update payload.

    Returns:
        Updated payload with derived achieved fields.
    """
    normalized = data.copy()

    if normalized.get("is_achieved") and "actual_date" not in normalized:
        achieved_date = normalized.get("achieved_date")
        normalized["actual_date"] = (
            achieved_date
            if isinstance(achieved_date, datetime)
            else datetime.now(UTC).replace(tzinfo=None)
        )

    if "actual_date" in normalized:
        if normalized["actual_date"] is None:
            normalized["is_achieved"] = False
            normalized.setdefault("achieved_date", None)
        else:
            normalized["is_achieved"] = True
            normalized.setdefault("achieved_date", normalized["actual_date"])

    return normalized


def _validate_milestone_date_range(
    project: Project,
    target_date: datetime | None,
    actual_date: datetime | None,
) -> ErrorResponse | None:
    """Validate milestone dates are within project date range.

    Args:
        project: Parent project.
        target_date: Planned milestone date.
        actual_date: Actual milestone date.

    Returns:
        Error response if validation fails, otherwise None.
    """
    start_date = _normalize_datetime(project.start_date)
    finish_date = _normalize_datetime(project.finish_date)

    if (
        target_date
        and start_date is not None
        and finish_date is not None
        and (target_date < start_date or target_date > finish_date)
    ):
        return {
            "error": UNPROCESSABLE_ENTITY_ERROR,
            "message": INVALID_TARGET_DATE_RANGE_MSG,
        }, 422

    if (
        actual_date
        and start_date is not None
        and finish_date is not None
        and (actual_date < start_date or actual_date > finish_date)
    ):
        return {
            "error": UNPROCESSABLE_ENTITY_ERROR,
            "message": INVALID_ACTUAL_DATE_RANGE_MSG,
        }, 422

    return None


def _validate_milestone_target_date_uniqueness(
    project_id: uuid.UUID,
    target_date: datetime | None,
    exclude_milestone_id: uuid.UUID | None = None,
) -> ErrorResponse | None:
    """Ensure milestone target_date is unique per project.

    Args:
        project_id: Project UUID.
        target_date: Target date to validate.
        exclude_milestone_id: Optional milestone ID to exclude (for updates).

    Returns:
        Error response if duplicate found, otherwise None.
    """
    if target_date is None:
        return None

    query = Milestone.query.filter_by(project_id=project_id, target_date=target_date)
    if exclude_milestone_id:
        query = query.filter(Milestone.id != exclude_milestone_id)

    if query.first():
        return {"error": BAD_REQUEST_ERROR, "message": MILESTONE_OVERLAP_MSG}, 400

    return None


def _calculate_budget_weight_sum(
    project_id: uuid.UUID, exclude_milestone_id: uuid.UUID | None = None
) -> Decimal:
    """Calculate the sum of budget_weight for all milestones in a project.

    Args:
        project_id: Project UUID.
        exclude_milestone_id: Optional milestone ID to exclude from sum.

    Returns:
        Sum of budget_weight values as Decimal.
    """
    query = db.session.query(func.sum(Milestone.budget_weight)).filter(
        Milestone.project_id == project_id
    )

    if exclude_milestone_id:
        query = query.filter(Milestone.id != exclude_milestone_id)

    result = query.scalar()
    return Decimal(result or 0)


def _validate_budget_weight_sum(
    project_id: uuid.UUID,
    new_weight: Decimal,
    exclude_milestone_id: uuid.UUID | None = None,
) -> tuple[bool, str | None]:
    """Validate that adding a new budget_weight won't exceed 1.0.

    Args:
        project_id: Project UUID.
        new_weight: New budget_weight to add.
        exclude_milestone_id: Optional milestone ID to exclude (for updates).

    Returns:
        Tuple of (is_valid, error_message).
    """
    current_sum = _calculate_budget_weight_sum(project_id, exclude_milestone_id)
    new_sum = current_sum + new_weight

    if new_sum > Decimal("1.0"):
        error_msg = BUDGET_WEIGHT_SUM_EXCEEDED_MSG.format(
            current=float(current_sum), adding=float(new_weight)
        )
        return False, error_msg

    return True, None


def _parse_uuid_param(
    value: str, message: str
) -> tuple[uuid.UUID | None, ErrorResponse | None]:
    """Parse UUID or return a standardized error response."""
    try:
        return uuid.UUID(value), None
    except ValueError:
        return None, ({"error": BAD_REQUEST_ERROR, "message": message}, 400)


def _get_project_or_404(
    project_uuid: uuid.UUID, company_id: uuid.UUID
) -> tuple[Project | None, ErrorResponse | None]:
    """Retrieve project scoped to company or return 404 error response."""
    project = Project.query.filter_by(id=project_uuid, company_id=company_id).first()
    if not project:
        return None, ({"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404)
    return project, None


def _parse_pagination_args(
    args: dict[str, str],
) -> tuple[tuple[int, int] | None, ErrorResponse | None]:
    """Validate and parse pagination parameters from query args."""
    try:
        page = int(args.get("page", 1))
        per_page = min(int(args.get("per_page", 20)), 100)
        if page < 1 or per_page < 1:
            raise ValueError
    except (TypeError, ValueError):
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_PAGINATION_MSG},
            400,
        )

    return (page, per_page), None


def _apply_milestone_filters(
    query, args: dict[str, str]
) -> tuple[Any | None, ErrorResponse | None]:
    """Apply filter parameters to the milestone query."""
    status = args.get("status")
    if status:
        if status not in ["upcoming", "achieved", "missed"]:
            return None, (
                {
                    "error": BAD_REQUEST_ERROR,
                    "message": INVALID_STATUS_MSG.format(status=status),
                },
                400,
            )
        query = query.filter(Milestone.status == status)

    target_date_from = args.get("target_date_from")
    if target_date_from:
        try:
            date_from = datetime.fromisoformat(target_date_from.replace("Z", "+00:00"))
            query = query.filter(
                Milestone.target_date >= _normalize_datetime(date_from)
            )
        except ValueError:
            return None, (
                {
                    "error": BAD_REQUEST_ERROR,
                    "message": "Invalid target_date_from format",
                },
                400,
            )

    target_date_to = args.get("target_date_to")
    if target_date_to:
        try:
            date_to = datetime.fromisoformat(target_date_to.replace("Z", "+00:00"))
            query = query.filter(Milestone.target_date <= _normalize_datetime(date_to))
        except ValueError:
            return None, (
                {
                    "error": BAD_REQUEST_ERROR,
                    "message": "Invalid target_date_to format",
                },
                400,
            )

    search = args.get("search")
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Milestone.name.ilike(search_pattern))
            | (Milestone.description.ilike(search_pattern))
        )

    return query, None


def _apply_milestone_sorting(
    query, sort_by: str, sort_order: str
) -> tuple[Any | None, ErrorResponse | None]:
    """Apply sorting to milestone query with validation."""
    if sort_by not in ["target_date", "name", "status", "budget_weight", "created_at"]:
        return None, (
            {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_BY_MSG.format(sort_by=sort_by),
            },
            400,
        )

    if sort_order not in ["asc", "desc"]:
        return None, (
            {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
            },
            400,
        )

    sort_column = getattr(Milestone, sort_by)
    query = query.order_by(
        sort_column.desc() if sort_order == "desc" else sort_column.asc()
    )
    return query, None


def _fetch_milestone_context(
    project_id: str, milestone_id: str, company_id: uuid.UUID
) -> tuple[
    uuid.UUID | None,
    uuid.UUID | None,
    Milestone | None,
    ErrorResponse | None,
]:
    """Resolve project and milestone with access checks."""
    project_uuid, error = _parse_uuid_param(
        project_id, INVALID_PROJECT_OR_MILESTONE_ID_MSG
    )
    if error:
        return None, None, None, error

    milestone_uuid, error = _parse_uuid_param(
        milestone_id, INVALID_PROJECT_OR_MILESTONE_ID_MSG
    )
    if error:
        return None, None, None, error

    project = Project.query.filter_by(id=project_uuid, company_id=company_id).first()
    if not project:
        return (
            project_uuid,
            milestone_uuid,
            None,
            (
                {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG},
                404,
            ),
        )

    milestone = Milestone.query.filter_by(
        id=milestone_uuid, project_id=project_uuid
    ).first()
    if not milestone:
        return (
            project_uuid,
            milestone_uuid,
            None,
            (
                {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG},
                404,
            ),
        )

    return project_uuid, milestone_uuid, milestone, None


def _load_milestone_update_payload() -> tuple[
    dict[str, Any] | None, ErrorResponse | None
]:
    """Load and validate milestone update payload."""
    if not request.is_json:
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG},
            400,
        )

    try:
        schema = MilestoneUpdateSchema()
        data = schema.load(request.json)
    except ValidationError as err:
        return None, (
            {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            },
            400,
        )

    if not isinstance(data, dict):
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG},
            400,
        )

    return _normalize_datetime_fields(data), None


class MilestoneListResource(Resource):
    """Resource for milestone collection operations.

    Handles:
    - GET /v0/projects/{project_id}/milestones - List milestones with pagination
    - POST /v0/projects/{project_id}/milestones - Create milestone
    """

    @require_jwt_auth
    @access_required(Operation.LIST, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self, project_id: str, version: str | None = None
    ) -> tuple[Any, int] | tuple[Any, int, dict[str, str]]:
        """Retrieve paginated list of milestones for a project.

        Supports filtering by status, target_date range, and text search.
        Supports sorting by multiple fields.

        Args:
            project_id: Project UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If project not found or wrong company.
            400: If pagination/filter parameters are invalid.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        project_uuid, error = _parse_uuid_param(
            project_id, INVALID_PROJECT_OR_MILESTONE_ID_MSG
        )
        if error:
            return error

        assert project_uuid is not None

        project, error = _get_project_or_404(project_uuid, company_id)
        if error:
            return error

        assert project is not None

        args = request.args.to_dict(flat=True)
        pagination, error = _parse_pagination_args(args)
        if error:
            return error
        assert pagination is not None
        page, per_page = pagination

        query = db.session.query(Milestone).filter(Milestone.project_id == project.id)

        filtered_query, error = _apply_milestone_filters(query, args)
        if error:
            return error
        assert filtered_query is not None
        query = filtered_query

        sort_by = args.get("sort_by", "target_date")
        sort_order = args.get("sort_order", "desc")
        sorted_query, error = _apply_milestone_sorting(query, sort_by, sort_order)
        if error:
            return error
        assert sorted_query is not None
        query = sorted_query

        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        milestones = query.limit(per_page).offset((page - 1) * per_page).all()

        schema = MilestoneSchema(many=True)
        data = schema.dump(milestones)

        response = {
            "data": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

        return response, 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def post(
        self, project_id: str, version: str | None = None
    ) -> tuple[Any, int] | tuple[Any, int, dict[str, str]]:
        """Create a new milestone for a project.

        Validates budget_weight sum doesn't exceed 1.0.

        Args:
            project_id: Project UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If project not found or wrong company.
            400: If validation fails.
            409: If budget_weight sum would exceed 1.0.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {"error": BAD_REQUEST_ERROR, "message": "Invalid project_id"}, 400

        # Verify project exists and belongs to company
        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404

        # Validate request body
        if not request.is_json:
            return {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG}, 400

        try:
            schema = MilestoneCreateSchema()
            data = schema.load(request.json)
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        # Normalize datetime fields
        if not isinstance(data, dict):
            return {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG}, 400
        data = _normalize_datetime_fields(data)

        date_error = _validate_milestone_date_range(
            project, data.get("target_date"), None
        )
        if date_error:
            return date_error

        overlap_error = _validate_milestone_target_date_uniqueness(
            project_uuid, data.get("target_date")
        )
        if overlap_error:
            return overlap_error

        # Validate budget_weight sum
        new_weight = Decimal(str(data["budget_weight"]))
        is_valid, error_msg = _validate_budget_weight_sum(project_uuid, new_weight)
        if not is_valid:
            return {"error": CONFLICT_ERROR, "message": error_msg}, 409

        # Create milestone
        milestone = Milestone(
            project_id=project_uuid,
            name=data["name"],
            description=data.get("description"),
            target_date=data["target_date"],
            budget_weight=new_weight,
            status="upcoming",
            is_achieved=False,
        )

        try:
            db.session.add(milestone)
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return {
                "error": CONFLICT_ERROR,
                "message": f"Database integrity error: {str(err.orig)}",
            }, 409

        # Serialize response
        milestone_schema = MilestoneSchema()
        response = {
            "data": milestone_schema.dump(milestone),
            "message": MILESTONE_CREATED_MSG,
        }

        return response, 201


class MilestoneResource(Resource):
    """Resource for individual milestone operations.

    Handles:
    - GET /v0/projects/{project_id}/milestones/{id} - Retrieve milestone
    - PATCH /v0/projects/{project_id}/milestones/{id} - Update milestone
    - DELETE /v0/projects/{project_id}/milestones/{id} - Delete milestone
    """

    @require_jwt_auth
    @access_required(Operation.READ, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self, project_id: str, id: str, version: str | None = None
    ) -> tuple[Any, int] | tuple[Any, int, dict[str, str]]:
        """Retrieve a single milestone by ID.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company/project.
            400: If ID format is invalid.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        _, _, milestone, error = _fetch_milestone_context(project_id, id, company_id)
        if error:
            return error

        assert milestone is not None

        schema = MilestoneSchema()
        response = {"data": schema.dump(milestone)}

        return response, 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def patch(
        self, project_id: str, id: str, version: str | None = None
    ) -> tuple[Any, int] | tuple[Any, int, dict[str, str]]:
        """Update a milestone (partial update).

        Validates budget_weight sum if budget_weight is updated.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company/project.
            400: If validation fails.
            409: If budget_weight sum would exceed 1.0.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        project_uuid, milestone_uuid, milestone, error = _fetch_milestone_context(
            project_id, id, company_id
        )
        if error:
            return error

        assert project_uuid is not None
        assert milestone_uuid is not None
        assert milestone is not None

        data, error = _load_milestone_update_payload()
        if error:
            return error

        assert data is not None

        # Validate budget_weight sum if updating budget_weight
        if "budget_weight" in data:
            new_weight = Decimal(str(data["budget_weight"]))
            is_valid, error_msg = _validate_budget_weight_sum(
                project_uuid, new_weight, exclude_milestone_id=milestone_uuid
            )
            if not is_valid:
                return {"error": CONFLICT_ERROR, "message": error_msg}, 409

        data = _prepare_milestone_update_data(data)

        project = milestone.project
        if project is None:
            return {
                "error": NOT_FOUND_ERROR,
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        date_error = _validate_milestone_date_range(
            project, data.get("target_date"), data.get("actual_date")
        )
        if date_error:
            return date_error

        overlap_error = _validate_milestone_target_date_uniqueness(
            project_uuid,
            data.get("target_date") or milestone.target_date,
            exclude_milestone_id=milestone_uuid,
        )
        if overlap_error:
            return overlap_error

        # Update fields
        for field, value in data.items():
            if field == "budget_weight":
                value = Decimal(str(value))
            setattr(milestone, field, value)

        milestone.status = _derive_milestone_status(
            milestone.target_date, milestone.actual_date
        )

        try:
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return {
                "error": CONFLICT_ERROR,
                "message": f"Database integrity error: {str(err.orig)}",
            }, 409

        # Serialize response
        milestone_schema = MilestoneSchema()
        response = {
            "data": milestone_schema.dump(milestone),
            "message": MILESTONE_UPDATED_MSG,
        }

        return response, 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def delete(
        self, project_id: str, id: str, version: str | None = None
    ) -> tuple[Any, int] | tuple[Any, int, dict[str, str]]:
        """Delete a milestone.

        Blocks deletion if milestone has associated expenses or deliverables.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (empty_dict, 204) on success.

        Raises:
            404: If milestone not found or wrong company/project.
            409: If milestone has associated expenses.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        _, _, milestone, error = _fetch_milestone_context(project_id, id, company_id)
        if error:
            return error

        assert milestone is not None

        # Check for associated expenses
        if milestone.expenses:
            return {
                "error": "Conflict",
                "message": CANNOT_DELETE_MILESTONE_WITH_EXPENSES_MSG.format(
                    count=len(milestone.expenses)
                ),
            }, 409

        # Delete milestone
        db.session.delete(milestone)
        db.session.commit()

        return "", 204
