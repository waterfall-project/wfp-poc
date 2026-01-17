# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Expense endpoints.

Implements CRUD and bulk operations for expenses with authentication,
authorization, validation, and pagination according to the OpenAPI contract.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.constants.http import (
    BAD_REQUEST_ERROR,
    CONFLICT_ERROR,
    INVALID_JSON_BODY_MSG,
    INVALID_PAGINATION_MSG,
    INVALID_PROJECT_ID_MSG,
    INVALID_REQUEST_MSG,
    INVALID_RESOURCE_ID_MSG,
    NOT_FOUND_ERROR,
    UNAUTHORIZED_ERROR,
    UNPROCESSABLE_ENTITY_ERROR,
    VALIDATION_FAILED_MSG,
)
from app.models.db import db
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.project import Project
from app.models.resource import Resource as ResourceModel
from app.schemas.expense_schema import (
    EXPENSE_CATEGORIES,
    ExpenseBulkCreateSchema,
    ExpenseBulkResponseSchema,
    ExpenseCreateSchema,
    ExpenseListResponseSchema,
    ExpenseResponseSchema,
    ExpenseSchema,
    ExpenseUpdateSchema,
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

if TYPE_CHECKING:
    from decimal import Decimal

# Error Messages
PROJECT_NOT_FOUND_MSG = "Project not found"
EXPENSE_NOT_FOUND_MSG = "Expense not found"
RESOURCE_NOT_FOUND_MSG = "Resource not found"
DUPLICATE_EXPENSE_MSG = "Duplicate expense detected"
EXPENSE_DATE_OUTSIDE_MILESTONE_RANGE_MSG = (
    "Expense date must fall between project milestone dates"
)
USER_CONTEXT_MISSING_MSG = "User context missing. Use @require_jwt_auth first."
INVALID_EXPENSE_ID_MSG = "Invalid expense id"
INVALID_MILESTONE_ID_MSG = "Invalid milestone_id"

# Success Messages
EXPENSE_CREATED_MSG = "Expense created and allocated to milestone"
EXPENSE_UPDATED_MSG = "Expense updated successfully"

ALLOWED_SORT_FIELDS = {
    "date": Expense.date,
    "amount": Expense.amount,
    "created_at": Expense.created_at,
    "updated_at": Expense.updated_at,
}


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a string into UUID, returning None when invalid."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string, returning None when invalid."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_expense_date(value: datetime) -> datetime:
    """Normalize a datetime for milestone comparisons (drop tzinfo)."""
    return value.replace(tzinfo=None)


def _get_project_scoped(
    project_id: uuid.UUID, company_id: uuid.UUID | None
) -> Project | None:
    """Retrieve project scoped to current company."""
    if not company_id:
        return None
    return Project.query.filter_by(id=project_id, company_id=company_id).first()


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


def _get_expense_scoped(expense_id: uuid.UUID, project_id: uuid.UUID) -> Expense | None:
    """Retrieve expense scoped to project."""
    return Expense.query.filter_by(id=expense_id, project_id=project_id).first()


def _get_json_object_or_error() -> tuple[dict[str, Any], ResponseTuple | None]:
    """Return JSON payload as dict or an error response when invalid."""
    json_payload_raw = request.get_json(silent=True)
    if json_payload_raw is None:
        return {}, None
    if isinstance(json_payload_raw, dict):
        return json_payload_raw, None
    return {}, _error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)


def _get_company_id_or_error() -> tuple[uuid.UUID | None, ResponseTuple | None]:
    """Return company UUID or an unauthorized error response."""
    company_id = get_current_company_uuid()
    if not company_id:
        return None, _error_response(
            USER_CONTEXT_MISSING_MSG, 401, error=UNAUTHORIZED_ERROR
        )
    return company_id, None


def _parse_pagination_or_error() -> tuple[int, int, ResponseTuple | None]:
    """Parse pagination parameters or return an error response."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        return (
            0,
            0,
            _error_response(INVALID_PAGINATION_MSG, 400, error=BAD_REQUEST_ERROR),
        )
    return page, per_page, None


def _apply_expense_filters(
    query,
) -> tuple[Any, ResponseTuple | None]:
    """Apply list filters to the expense query."""
    category_filter = request.args.get("category")
    if category_filter:
        if category_filter not in EXPENSE_CATEGORIES:
            return None, _error_response(
                INVALID_REQUEST_MSG, 400, error=BAD_REQUEST_ERROR
            )
        query = query.filter(Expense.category == category_filter)

    milestone_filter = request.args.get("milestone_id")
    if milestone_filter:
        milestone_uuid = _parse_uuid(milestone_filter)
        if not milestone_uuid:
            return None, _error_response(
                INVALID_MILESTONE_ID_MSG, 400, error=BAD_REQUEST_ERROR
            )
        query = query.filter(Expense.milestone_id == milestone_uuid)

    resource_filter = request.args.get("resource_id")
    if resource_filter:
        resource_uuid = _parse_uuid(resource_filter)
        if not resource_uuid:
            return None, _error_response(
                INVALID_RESOURCE_ID_MSG, 400, error=BAD_REQUEST_ERROR
            )
        query = query.filter(Expense.resource_id == resource_uuid)

    date_from_raw = request.args.get("date_from")
    if date_from_raw:
        date_from = _parse_datetime(date_from_raw)
        if not date_from:
            return None, _error_response(
                INVALID_REQUEST_MSG, 400, error=BAD_REQUEST_ERROR
            )
        query = query.filter(Expense.date >= date_from)

    date_to_raw = request.args.get("date_to")
    if date_to_raw:
        date_to = _parse_datetime(date_to_raw)
        if not date_to:
            return None, _error_response(
                INVALID_REQUEST_MSG, 400, error=BAD_REQUEST_ERROR
            )
        query = query.filter(Expense.date <= date_to)

    return query, None


def _get_sort_clause_or_error() -> tuple[Any, ResponseTuple | None]:
    """Return sort clause or an error response."""
    sort_by = request.args.get("sort_by", "date")
    sort_order = request.args.get("sort_order", "desc")

    sort_column = ALLOWED_SORT_FIELDS.get(sort_by)
    if not sort_column:
        return None, _error_response(INVALID_REQUEST_MSG, 400, error=BAD_REQUEST_ERROR)
    if sort_order not in {"asc", "desc"}:
        return None, _error_response(INVALID_REQUEST_MSG, 400, error=BAD_REQUEST_ERROR)

    order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    return order_clause, None


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


def _get_expense_or_error(
    project: Project, expense_id: str
) -> tuple[Expense | None, ResponseTuple | None]:
    """Return expense or an error response for invalid/missing expense."""
    expense_uuid = _parse_uuid(expense_id)
    if not expense_uuid:
        return None, _error_response(
            INVALID_EXPENSE_ID_MSG, 400, error=BAD_REQUEST_ERROR
        )

    expense = _get_expense_scoped(expense_uuid, project.id)
    if not expense:
        return None, _error_response(EXPENSE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR)

    return expense, None


def _get_milestones_for_project(project_id: uuid.UUID) -> list[Milestone]:
    """Return milestones ordered by target_date for the project."""
    return (
        Milestone.query.filter_by(project_id=project_id)
        .order_by(Milestone.target_date.asc())
        .all()
    )


def _select_milestone_for_date(
    milestones: list[Milestone], expense_date: datetime
) -> Milestone | None:
    """Select milestone matching expense date based on target_date boundaries."""
    if not milestones:
        return None

    normalized_date = _normalize_expense_date(expense_date)
    if normalized_date < milestones[0].target_date:
        return None
    if normalized_date > milestones[-1].target_date:
        return None

    for milestone in milestones:
        if normalized_date <= milestone.target_date:
            return milestone

    return None


def _get_milestone_for_expense_or_error(
    project: Project, expense_date: datetime
) -> tuple[Milestone | None, ResponseTuple | None]:
    """Return milestone for expense date or an error response when invalid."""
    milestones = _get_milestones_for_project(project.id)
    milestone = _select_milestone_for_date(milestones, expense_date)
    if not milestone:
        return None, _error_response(
            EXPENSE_DATE_OUTSIDE_MILESTONE_RANGE_MSG,
            422,
            error=UNPROCESSABLE_ENTITY_ERROR,
        )
    return milestone, None


def _is_duplicate_expense(
    project_id: uuid.UUID, reference_number: str | None, date: datetime, amount: Decimal
) -> bool:
    """Return True when an expense with the same import signature exists."""
    if not reference_number:
        return False
    return (
        Expense.query.filter_by(
            project_id=project_id,
            reference_number=reference_number,
            date=date,
            amount=amount,
        ).first()
        is not None
    )


def _build_duplicate_key(
    reference_number: str, date: datetime, amount: Decimal
) -> tuple[str, str, str]:
    """Build a hashable duplicate detection key."""
    return reference_number, date.isoformat(), str(amount)


def _process_bulk_expenses(
    project: Project,
    company_id: uuid.UUID,
    expenses_payload: list[dict[str, Any]],
) -> tuple[list[Expense], list[dict[str, Any]]]:
    """Validate and build expenses for bulk creation."""
    milestones = _get_milestones_for_project(project.id)
    created_expenses: list[Expense] = []
    errors: list[dict[str, Any]] = []

    reference_numbers = {
        item.get("reference_number")
        for item in expenses_payload
        if item.get("reference_number")
    }

    existing_keys: set[tuple[str, str, str]] = set()
    if reference_numbers:
        existing = Expense.query.filter(
            Expense.project_id == project.id,
            Expense.reference_number.in_(reference_numbers),
        ).all()
        for expense in existing:
            if expense.reference_number:
                existing_keys.add(
                    _build_duplicate_key(
                        expense.reference_number, expense.date, expense.amount
                    )
                )

    batch_keys: set[tuple[str, str, str]] = set()

    for index, item in enumerate(expenses_payload):
        expense, error, duplicate_key = _build_bulk_expense(
            project,
            company_id,
            milestones,
            item,
            index,
            existing_keys,
            batch_keys,
        )
        if error:
            errors.append(error)
            continue
        if duplicate_key:
            batch_keys.add(duplicate_key)
        if expense:
            created_expenses.append(expense)
            db.session.add(expense)

    return created_expenses, errors


def _build_bulk_expense(
    project: Project,
    company_id: uuid.UUID,
    milestones: list[Milestone],
    item: dict[str, Any],
    index: int,
    existing_keys: set[tuple[str, str, str]],
    batch_keys: set[tuple[str, str, str]],
) -> tuple[Expense | None, dict[str, Any] | None, tuple[str, str, str] | None]:
    """Build a bulk expense instance or return an error payload."""
    resource = None
    resource_id = item.get("resource_id")
    if resource_id:
        resource = _get_resource_scoped(str(resource_id), company_id)
        if not resource:
            return None, {"index": index, "error": RESOURCE_NOT_FOUND_MSG}, None

    expense_date = item["date"]
    milestone = _select_milestone_for_date(milestones, expense_date)
    if not milestone:
        return (
            None,
            {"index": index, "error": EXPENSE_DATE_OUTSIDE_MILESTONE_RANGE_MSG},
            None,
        )

    amount = item["amount"]
    reference_number = item.get("reference_number")
    duplicate_key = None
    if reference_number:
        duplicate_key = _build_duplicate_key(reference_number, expense_date, amount)
        if duplicate_key in existing_keys or duplicate_key in batch_keys:
            return None, {"index": index, "error": DUPLICATE_EXPENSE_MSG}, None

    expense = Expense(
        project_id=project.id,
        date=expense_date,
        amount=amount,
        category=item["category"],
        description=item.get("description"),
        milestone_id=milestone.id,
        resource_id=resource.id if resource else None,
        reference_number=reference_number,
        purchase_document=item.get("purchase_document"),
        fiscal_year=item.get("fiscal_year"),
        period=item.get("period"),
        otp_element=item.get("otp_element"),
        accounting_nature=item.get("accounting_nature"),
        vendor_name=item.get("vendor_name"),
        origin_group=item.get("origin_group"),
    )

    return expense, None, duplicate_key


class ExpenseListResource(Resource):
    """REST resource for collection operations on expenses."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.expense_schema = ExpenseSchema()
        self.response_schema = ExpenseResponseSchema()
        self.list_schema = ExpenseListResponseSchema()
        self.create_schema = ExpenseCreateSchema()

    @require_jwt_auth
    @access_required(Operation.LIST, "expenses")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """List expenses for a project with pagination and filters."""
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

        page, per_page, pagination_error = _parse_pagination_or_error()
        if pagination_error:
            return pagination_error

        query = Expense.query.filter_by(project_id=project.id)
        query, filter_error = _apply_expense_filters(query)
        if filter_error:
            return filter_error

        order_clause, sort_error = _get_sort_clause_or_error()
        if sort_error:
            return sort_error

        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 0

        expenses = (
            query.order_by(order_clause)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        data = self.list_schema.dump(
            {
                "data": expenses,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            }
        )

        return data, 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "expenses")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def post(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Create a new expense."""
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

        resource_id = data.get("resource_id")
        if resource_id:
            resource = _get_resource_scoped(str(resource_id), company_id)
            if not resource:
                return _error_response(
                    RESOURCE_NOT_FOUND_MSG, 404, error=NOT_FOUND_ERROR
                )
        else:
            resource = None

        expense_date = data["date"]
        milestone, milestone_error = _get_milestone_for_expense_or_error(
            project, expense_date
        )
        if milestone_error:
            return milestone_error

        assert milestone is not None

        amount = data["amount"]
        reference_number = data.get("reference_number")
        if _is_duplicate_expense(project.id, reference_number, expense_date, amount):
            return _error_response(DUPLICATE_EXPENSE_MSG, 409, error=CONFLICT_ERROR)

        expense = Expense(
            project_id=project.id,
            date=expense_date,
            amount=amount,
            category=data["category"],
            description=data.get("description"),
            milestone_id=milestone.id,
            resource_id=resource.id if resource else None,
            reference_number=reference_number,
            purchase_document=data.get("purchase_document"),
            fiscal_year=data.get("fiscal_year"),
            period=data.get("period"),
            otp_element=data.get("otp_element"),
            accounting_nature=data.get("accounting_nature"),
            vendor_name=data.get("vendor_name"),
            origin_group=data.get("origin_group"),
        )

        try:
            db.session.add(expense)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return _error_response(DUPLICATE_EXPENSE_MSG, 409, error=CONFLICT_ERROR)

        response_data = self.response_schema.dump(
            {"data": expense, "message": EXPENSE_CREATED_MSG}
        )
        return response_data, 201


class ExpenseBulkResource(Resource):
    """REST resource for bulk expense creation."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.bulk_schema = ExpenseBulkCreateSchema()
        self.response_schema = ExpenseBulkResponseSchema()

    @require_jwt_auth
    @access_required(Operation.CREATE, "expenses")
    @limiter.limit("10 per minute", key_func=rate_limit_user_key)
    def post(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Bulk create expenses."""
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
            loaded = self.bulk_schema.load(payload)
        except ValidationError as err:
            return _error_response(
                VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR, errors=err.messages
            )

        if not isinstance(loaded, dict):
            return _error_response(VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR)

        expenses_payload: list[dict[str, Any]] = loaded.get("expenses", [])
        created_expenses, errors = _process_bulk_expenses(
            project, company_id, expenses_payload
        )

        if created_expenses:
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                return _error_response(DUPLICATE_EXPENSE_MSG, 409, error=CONFLICT_ERROR)

        created_count = len(created_expenses)
        failed_count = len(errors)
        message = f"{created_count} expenses created, {failed_count} failed"

        response_data = self.response_schema.dump(
            {
                "data": {
                    "created_count": created_count,
                    "failed_count": failed_count,
                    "expenses": created_expenses,
                    "errors": errors,
                },
                "message": message,
            }
        )
        return response_data, 201


class ExpenseResource(Resource):
    """REST resource for item operations on expenses."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.expense_schema = ExpenseSchema()
        self.response_schema = ExpenseResponseSchema()
        self.update_schema = ExpenseUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "expenses")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Retrieve a single expense by ID."""
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
        expense, expense_error = _get_expense_or_error(project, id)
        if expense_error:
            return expense_error

        assert expense is not None

        response_data = self.response_schema.dump({"data": expense})
        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "expenses")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def patch(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Partially update an expense."""
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
        expense, expense_error = _get_expense_or_error(project, id)
        if expense_error:
            return expense_error

        assert expense is not None

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

        if "date" in data:
            new_date = data["date"]
            milestone, milestone_error = _get_milestone_for_expense_or_error(
                project, new_date
            )
            if milestone_error:
                return milestone_error
            assert milestone is not None
            expense.date = new_date
            expense.milestone_id = milestone.id

        if "amount" in data:
            expense.amount = data["amount"]
        if "category" in data:
            expense.category = data["category"]
        if "description" in data:
            expense.description = data["description"]

        db.session.commit()

        response_data = self.response_schema.dump(
            {"data": expense, "message": EXPENSE_UPDATED_MSG}
        )
        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "expenses")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def delete(
        self, project_id: str, id: str, version: str | None = None
    ) -> ResponseTuple:
        """Delete an expense."""
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
        expense, expense_error = _get_expense_or_error(project, id)
        if expense_error:
            return expense_error

        assert expense is not None

        db.session.delete(expense)
        db.session.commit()
        return "", 204
