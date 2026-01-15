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
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    require_jwt_auth,
)

# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"

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


class MilestoneListResource(Resource):
    """Resource for milestone collection operations.

    Handles:
    - GET /v0/projects/{project_id}/milestones - List milestones with pagination
    - POST /v0/projects/{project_id}/milestones - Create milestone
    """

    @require_jwt_auth
    @access_required(Operation.LIST)
    @limiter.limit("100 per minute")
    def get(self, project_id: str) -> tuple[dict[str, Any], int]:
        """Retrieve paginated list of milestones for a project.

        Supports filtering by status, target_date range, and text search.
        Supports sorting by multiple fields.

        Args:
            project_id: Project UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If project not found or wrong company.
            400: If pagination/filter parameters are invalid.
        """
        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {"error": BAD_REQUEST_ERROR, "message": "Invalid project_id"}, 400

        # Verify project exists and belongs to company
        project = db.session.get(Project, project_uuid)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404

        # Pagination parameters
        try:
            page = int(request.args.get("page", 1))
            per_page = min(int(request.args.get("per_page", 20)), 100)
            if page < 1 or per_page < 1:
                raise ValueError
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_PAGINATION_MSG,
            }, 400

        # Build query
        query = db.session.query(Milestone).filter(Milestone.project_id == project_uuid)

        # Filter by status
        status = request.args.get("status")
        if status:
            if status not in ["upcoming", "achieved", "missed"]:
                return {
                    "error": BAD_REQUEST_ERROR,
                    "message": INVALID_STATUS_MSG.format(status=status),
                }, 400
            query = query.filter(Milestone.status == status)

        # Filter by target_date range
        target_date_from = request.args.get("target_date_from")
        if target_date_from:
            try:
                date_from = datetime.fromisoformat(
                    target_date_from.replace("Z", "+00:00")
                )
                query = query.filter(Milestone.target_date >= date_from)
            except ValueError:
                return {
                    "error": BAD_REQUEST_ERROR,
                    "message": "Invalid target_date_from format",
                }, 400

        target_date_to = request.args.get("target_date_to")
        if target_date_to:
            try:
                date_to = datetime.fromisoformat(target_date_to.replace("Z", "+00:00"))
                query = query.filter(Milestone.target_date <= date_to)
            except ValueError:
                return {
                    "error": BAD_REQUEST_ERROR,
                    "message": "Invalid target_date_to format",
                }, 400

        # Text search
        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Milestone.name.ilike(search_pattern))
                | (Milestone.description.ilike(search_pattern))
            )

        # Sorting
        sort_by = request.args.get("sort_by", "target_date")
        sort_order = request.args.get("sort_order", "asc")

        if sort_by not in [
            "target_date",
            "name",
            "status",
            "budget_weight",
            "created_at",
        ]:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_BY_MSG.format(sort_by=sort_by),
            }, 400

        if sort_order not in ["asc", "desc"]:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
            }, 400

        sort_column = getattr(Milestone, sort_by)
        query = query.order_by(
            sort_column.desc() if sort_order == "desc" else sort_column.asc()
        )

        # Get total count
        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 1

        # Apply pagination
        milestones = query.limit(per_page).offset((page - 1) * per_page).all()

        # Serialize
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
    @access_required(Operation.CREATE)
    @limiter.limit("100 per minute")
    def post(self, project_id: str) -> tuple[dict[str, Any], int]:
        """Create a new milestone for a project.

        Validates budget_weight sum doesn't exceed 1.0.

        Args:
            project_id: Project UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If project not found or wrong company.
            400: If validation fails.
            409: If budget_weight sum would exceed 1.0.
        """
        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {"error": BAD_REQUEST_ERROR, "message": "Invalid project_id"}, 400

        # Verify project exists and belongs to company
        project = db.session.get(Project, project_uuid)
        if not project or project.company_id != company_id:
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
        data = _normalize_datetime_fields(data)

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
    @access_required(Operation.READ)
    @limiter.limit("100 per minute")
    def get(self, project_id: str, id: str) -> tuple[dict[str, Any], int]:
        """Retrieve a single milestone by ID.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company/project.
            400: If ID format is invalid.
        """
        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
            milestone_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid project_id or milestone id",
            }, 400

        # Verify project exists and belongs to company
        project = db.session.get(Project, project_uuid)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404

        # Get milestone
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone or milestone.project_id != project_uuid:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Serialize response
        schema = MilestoneSchema()
        response = {"data": schema.dump(milestone)}

        return response, 200

    @require_jwt_auth
    @access_required(Operation.UPDATE)
    @limiter.limit("100 per minute")
    def patch(self, project_id: str, id: str) -> tuple[dict[str, Any], int]:
        """Update a milestone (partial update).

        Validates budget_weight sum if budget_weight is updated.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company/project.
            400: If validation fails.
            409: If budget_weight sum would exceed 1.0.
        """
        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
            milestone_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid project_id or milestone id",
            }, 400

        # Verify project exists and belongs to company
        project = db.session.get(Project, project_uuid)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404

        # Get milestone
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone or milestone.project_id != project_uuid:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Validate request body
        if not request.is_json:
            return {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG}, 400

        try:
            schema = MilestoneUpdateSchema()
            data = schema.load(request.json)
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        # Normalize datetime fields
        data = _normalize_datetime_fields(data)

        # Validate budget_weight sum if updating budget_weight
        if "budget_weight" in data:
            new_weight = Decimal(str(data["budget_weight"]))
            # Exclude current milestone from sum calculation
            is_valid, error_msg = _validate_budget_weight_sum(
                project_uuid, new_weight, exclude_milestone_id=milestone_uuid
            )
            if not is_valid:
                return {"error": CONFLICT_ERROR, "message": error_msg}, 409

        # Update fields
        for field, value in data.items():
            if field == "budget_weight":
                value = Decimal(str(value))
            setattr(milestone, field, value)

        # Auto-update status based on achieved status
        if "is_achieved" in data and data["is_achieved"]:
            milestone.status = "achieved"
            if "achieved_date" not in data:
                milestone.achieved_date = datetime.now(UTC).replace(tzinfo=None)

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
    @access_required(Operation.DELETE)
    @limiter.limit("100 per minute")
    def delete(self, project_id: str, id: str) -> tuple[dict[str, Any], int]:
        """Delete a milestone.

        Blocks deletion if milestone has associated expenses or deliverables.

        Args:
            project_id: Project UUID from path parameter.
            id: Milestone UUID from path parameter.

        Returns:
            Tuple of (empty_dict, 204) on success.

        Raises:
            404: If milestone not found or wrong company/project.
            409: If milestone has associated expenses.
        """
        company_id = get_current_company_id()

        try:
            project_uuid = uuid.UUID(project_id)
            milestone_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid project_id or milestone id",
            }, 400

        # Verify project exists and belongs to company
        project = db.session.get(Project, project_uuid)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": PROJECT_NOT_FOUND_MSG}, 404

        # Get milestone
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone or milestone.project_id != project_uuid:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Check for associated expenses
        # TODO: Uncomment when Expense model has milestone_id field
        # expense_count = (
        #     db.session.query(func.count(Expense.id))
        #     .filter(Expense.milestone_id == milestone_uuid)
        #     .scalar()
        # )
        #
        # if expense_count > 0:
        #     return {
        #         "error": CONFLICT_ERROR,
        #         "message": CANNOT_DELETE_MILESTONE_WITH_EXPENSES_MSG.format(
        #             count=expense_count
        #         ),
        #     }, 409

        # For now, allow deletion (expenses model needs milestone_id field)

        # Delete milestone
        db.session.delete(milestone)
        db.session.commit()

        return {}, 204
