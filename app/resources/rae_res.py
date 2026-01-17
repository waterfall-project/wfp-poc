# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for RAE endpoints.

Implements milestone RAE update, history retrieval, and project summary.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeAlias, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.db import db
from app.models.milestone import Milestone
from app.models.milestone_rae import MilestoneRAE
from app.models.project import Project
from app.schemas.rae_schema import (
    RAECreateSchema,
    RAEHistoryQuerySchema,
    RAEHistoryResponseSchema,
    RAEResponseSchema,
    RAESummaryQuerySchema,
    RAESummaryResponseSchema,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version_or_error_response
from app.utils.correlation import error_response
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    get_current_user_id,
    require_jwt_auth,
)
from app.utils.rate_limit import rate_limit_user_key

ResponseTuple = tuple[dict[str, Any], int] | tuple[dict[str, Any], int, dict[str, str]]

# Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"

# Error Messages
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
MILESTONE_NOT_FOUND_MSG = "Milestone not found"
PROJECT_NOT_FOUND_MSG = "Project not found"
INVALID_COMPANY_ID_CLAIM_MSG = "Invalid token: company_id claim is not a valid UUID."
INVALID_USER_ID_CLAIM_MSG = "Invalid token: user_id claim is not a valid UUID."


# Success Messages
RAE_UPDATED_MSG = "RAE updated successfully"

DictStrAny: TypeAlias = dict[str, Any]


def _normalize_datetime(value: datetime | None) -> datetime | None:
    """Normalize datetime to naive UTC for storage consistency."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _normalize_details(details: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert non-JSON-native values within details to serializable forms."""
    if details is None:
        return None

    def _convert_value(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {key: _convert_value(val) for key, val in value.items()}
        if isinstance(value, list):
            return [_convert_value(item) for item in value]
        return value

    return cast("dict[str, Any]", _convert_value(details))


def _get_latest_entries(
    milestone_ids: list[uuid.UUID],
    as_of_date: datetime | None,
) -> dict[uuid.UUID, MilestoneRAE]:
    """Fetch latest RAE entries per milestone up to as_of_date."""
    latest_entries: dict[uuid.UUID, MilestoneRAE] = {}
    if not milestone_ids:
        return latest_entries

    query = MilestoneRAE.query.filter(MilestoneRAE.milestone_id.in_(milestone_ids))
    if as_of_date is not None:
        query = query.filter(MilestoneRAE.date <= as_of_date)

    entries = query.order_by(MilestoneRAE.milestone_id, MilestoneRAE.date.desc()).all()
    for entry in entries:
        if entry.milestone_id not in latest_entries:
            latest_entries[entry.milestone_id] = entry
    return latest_entries


def _get_company_uuid_or_error() -> tuple[uuid.UUID | None, ResponseTuple | None]:
    """Get company UUID from JWT context or return error response."""
    company_id = get_current_company_id()
    try:
        return uuid.UUID(str(company_id)), None
    except (TypeError, ValueError):
        return None, error_response(
            INVALID_COMPANY_ID_CLAIM_MSG, 401, error="Unauthorized"
        )


def _get_user_uuid_or_error() -> tuple[uuid.UUID | None, ResponseTuple | None]:
    """Get user UUID from JWT context or return error response."""
    user_id = get_current_user_id()
    try:
        return uuid.UUID(str(user_id)), None
    except (TypeError, ValueError):
        return None, error_response(
            INVALID_USER_ID_CLAIM_MSG, 401, error="Unauthorized"
        )


def _get_milestone_or_error(
    milestone_id: str, company_id: uuid.UUID
) -> tuple[Milestone | None, ResponseTuple | None]:
    """Get milestone scoped to company or return error response."""
    try:
        milestone_uuid = uuid.UUID(milestone_id)
    except ValueError:
        return None, error_response(
            "Invalid milestone_id", 400, error=BAD_REQUEST_ERROR
        )

    milestone = (
        Milestone.query.join(Project, Project.id == Milestone.project_id)
        .filter(Milestone.id == milestone_uuid, Project.company_id == company_id)
        .first()
    )
    if not milestone:
        return None, error_response(MILESTONE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)
    return milestone, None


def _get_project_or_error(
    project_id: str, company_id: uuid.UUID
) -> tuple[Project | None, ResponseTuple | None]:
    """Get project scoped to company or return error response."""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        return None, error_response("Invalid project_id", 400, error=BAD_REQUEST_ERROR)

    project = Project.query.filter_by(id=project_uuid, company_id=company_id).first()
    if not project:
        return None, error_response(PROJECT_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)
    return project, None


class MilestoneRAEResource(Resource):
    """Resource for updating milestone RAE values."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.create_schema = RAECreateSchema()
        self.response_schema = RAEResponseSchema()

    @require_jwt_auth
    @access_required(Operation.CREATE, "rae")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def post(self, milestone_id: str, version: str | None = None) -> ResponseTuple:
        """Create a new milestone RAE entry.

        Returns:
            Tuple with response body, status, and headers.
        """
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        if not request.is_json:
            return error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        raw_payload = request.get_json()
        if not isinstance(raw_payload, dict):
            return error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        try:
            payload = self.create_schema.load(raw_payload)
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        if not isinstance(payload, dict):
            return error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err

        assert company_id is not None

        user_id, user_err = _get_user_uuid_or_error()
        if user_err:
            return user_err

        assert user_id is not None

        milestone, milestone_err = _get_milestone_or_error(milestone_id, company_id)
        if milestone_err:
            return milestone_err

        assert milestone is not None

        rae_date = _normalize_datetime(payload["date"])
        assert rae_date is not None
        amount = payload["amount"]
        comment = payload.get("comment")
        details = _normalize_details(payload.get("details"))

        rae_entry = MilestoneRAE(
            milestone_id=milestone.id,
            date=rae_date,
            amount=amount,
            updated_by=user_id,
            comment=comment,
            details=details,
        )

        try:
            db.session.add(rae_entry)
            milestone.current_rae = Decimal(str(amount))
            milestone.current_rae_date = rae_date
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            return error_response(
                "RAE entry already exists for this date",
                400,
                error=BAD_REQUEST_ERROR,
                errors={"detail": str(exc)},
            )

        response = cast(
            "DictStrAny",
            self.response_schema.dump(
                {
                    "data": rae_entry,
                    "message": RAE_UPDATED_MSG,
                }
            ),
        )
        return response, 201


class MilestoneRAEHistoryResource(Resource):
    """Resource for milestone RAE history retrieval."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.query_schema = RAEHistoryQuerySchema()
        self.response_schema = RAEHistoryResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "rae")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, milestone_id: str, version: str | None = None) -> ResponseTuple:
        """Retrieve paginated RAE history for a milestone."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err

        assert company_id is not None

        milestone, milestone_err = _get_milestone_or_error(milestone_id, company_id)
        if milestone_err:
            return milestone_err
        assert milestone is not None

        try:
            query_params = self.query_schema.load(request.args)
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        if not isinstance(query_params, dict):
            return error_response(VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR)

        page = query_params["page"]
        per_page = query_params["per_page"]
        date_from = query_params.get("date_from")
        date_to = query_params.get("date_to")
        sort_order = query_params["sort_order"]

        query = MilestoneRAE.query.filter_by(milestone_id=milestone.id)
        if date_from:
            query = query.filter(MilestoneRAE.date >= date_from)
        if date_to:
            query = query.filter(MilestoneRAE.date <= date_to)

        if sort_order == "asc":
            query = query.order_by(MilestoneRAE.date.asc())
        else:
            query = query.order_by(MilestoneRAE.date.desc())

        total = query.count()
        entries = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = math.ceil(total / per_page) if per_page else 0

        response = cast(
            "DictStrAny",
            self.response_schema.dump(
                {
                    "data": entries,
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                }
            ),
        )
        return response, 200


class ProjectRAESummaryResource(Resource):
    """Resource for project-wide RAE summary."""

    def __init__(self) -> None:
        """Initialize resource with schema dependencies."""
        self.query_schema = RAESummaryQuerySchema()
        self.response_schema = RAESummaryResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "rae")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Retrieve project-wide RAE summary."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_err = _get_company_uuid_or_error()
        if company_err:
            return company_err

        assert company_id is not None

        project, project_err = _get_project_or_error(project_id, company_id)
        if project_err:
            return project_err

        assert project is not None

        try:
            query_params = self.query_schema.load(request.args)
        except ValidationError as exc:
            return error_response(
                VALIDATION_FAILED_MSG,
                400,
                error=BAD_REQUEST_ERROR,
                errors=exc.messages,
            )

        if not isinstance(query_params, dict):
            return error_response(VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR)

        as_of_date = _normalize_datetime(query_params.get("as_of_date"))

        milestones = Milestone.query.filter_by(project_id=project.id).all()
        milestone_ids = [milestone.id for milestone in milestones]
        latest_entries = _get_latest_entries(milestone_ids, as_of_date)

        if as_of_date is None:
            candidate_dates: list[datetime] = [
                entry.date for entry in latest_entries.values()
            ]
            candidate_dates.extend(
                milestone.current_rae_date
                for milestone in milestones
                if milestone.current_rae_date is not None
            )
            if candidate_dates:
                as_of_date = max(candidate_dates)
            else:
                as_of_date = _normalize_datetime(datetime.now(UTC))

        assert as_of_date is not None

        summary_items: list[dict[str, Any]] = []
        total_rae = Decimal("0")

        for milestone in milestones:
            entry = latest_entries.get(milestone.id)
            if entry:
                rae_value = Decimal(str(entry.amount))
                rae_date = entry.date
                comment = entry.comment
            else:
                rae_value = Decimal(str(milestone.current_rae or 0))
                rae_date = milestone.current_rae_date
                comment = None

            total_rae += rae_value
            summary_items.append(
                {
                    "milestone_id": milestone.id,
                    "name": milestone.name,
                    "budget_weight": milestone.budget_weight,
                    "rae": rae_value,
                    "rae_date": rae_date,
                    "achieved": bool(milestone.is_achieved),
                    "comment": comment,
                }
            )

        response = cast(
            "DictStrAny",
            self.response_schema.dump(
                {
                    "data": {
                        "project_id": project.id,
                        "as_of_date": as_of_date,
                        "total_rae": total_rae,
                        "milestones": summary_items,
                    }
                }
            ),
        )
        return response, 200
