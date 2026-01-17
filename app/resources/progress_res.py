# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for progress update endpoints.

Implements bulk progress updates and progress history retrieval for projects.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.db import db
from app.models.progress_update import ProgressUpdate
from app.models.project import Project
from app.models.task import Task
from app.schemas.progress_schema import (
    ProgressHistoryQuerySchema,
    ProgressHistoryResponseSchema,
    ProgressUpdateRequestSchema,
    ProgressUpdateResponseSchema,
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
ProgressPayload = dict[str, Any]
QueryParams = dict[str, Any]

# Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"

# Error Messages
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
PROJECT_NOT_FOUND_MSG = "Project not found"
TASK_NOT_FOUND_MSG = "Task not found"
TASK_COMPLETED_MSG = "Cannot update completed task"
TASK_CANCELLED_MSG = "Cannot update cancelled task"
INVALID_COMPANY_ID_CLAIM_MSG = "Invalid token: company_id claim is not a valid UUID."
INVALID_USER_ID_CLAIM_MSG = "Invalid token: user_id claim is not a valid UUID."

# Success Messages
PROGRESS_UPDATED_MSG = "Progress updated successfully"


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize datetime to naive UTC for consistent storage."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _derive_status(percent_complete: int) -> str:
    """Derive task status from percent_complete."""
    if percent_complete <= 0:
        return "not_started"
    if percent_complete >= 100:
        return "completed"
    return "in_progress"


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


def _build_history_item(update: ProgressUpdate, task_name: str) -> dict[str, Any]:
    """Build a progress history response item."""
    previous = int(round(float(update.previous_percent_complete or 0)))
    new = int(round(float(update.percent_complete or 0)))

    return {
        "id": str(update.id),
        "project_id": str(update.project_id),
        "task_id": str(update.task_id),
        "task_name": task_name,
        "date": update.update_date,
        "previous_percent_complete": previous,
        "new_percent_complete": new,
        "delta": new - previous,
        "comment": update.notes,
        "updated_by": str(update.updated_by),
        "created_at": update.created_at,
    }


def _rollup_summary_tasks(updated_task_ids: set[uuid.UUID]) -> None:
    """Recalculate summary task progress for parents of updated tasks."""
    parent_ids: set[uuid.UUID] = set()
    if not updated_task_ids:
        return

    tasks = Task.query.filter(Task.id.in_(list(updated_task_ids))).all()
    parent_ids.update(task.parent_id for task in tasks if task.parent_id)

    while parent_ids:
        current_ids = list(parent_ids)
        parent_ids.clear()
        parents = Task.query.filter(Task.id.in_(current_ids)).all()

        for parent in parents:
            _update_summary_task(parent, parent_ids)


def _update_summary_task(parent: Task, parent_ids: set[uuid.UUID]) -> None:
    """Update a summary task based on its children."""
    if parent.type != "summary":
        if parent.parent_id:
            parent_ids.add(parent.parent_id)
        return

    children = Task.query.filter_by(parent_id=parent.id).all()
    if not children:
        return

    avg = sum(float(child.percent_complete) for child in children) / len(children)
    parent.percent_complete = float(avg)
    if parent.status != "cancelled":
        parent.status = _derive_status(int(round(avg)))

    if parent.parent_id:
        parent_ids.add(parent.parent_id)


def _process_progress_updates(
    updates: list[dict[str, Any]],
    task_map: dict[uuid.UUID, Task],
    project: Project,
    report_date: datetime,
    user_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[uuid.UUID]]:
    """Process progress updates and return success/error details."""
    success_items: list[dict[str, Any]] = []
    error_items: list[dict[str, Any]] = []
    updated_task_ids: set[uuid.UUID] = set()

    for item in updates:
        task_id = item["task_id"]
        percent_complete = int(item["percent_complete"])
        comment = item.get("comment")

        task = task_map.get(task_id)
        if not task:
            error_items.append({"task_id": str(task_id), "error": TASK_NOT_FOUND_MSG})
            continue

        if task.status == "completed":
            error_items.append({"task_id": str(task_id), "error": TASK_COMPLETED_MSG})
            continue

        if task.status == "cancelled":
            error_items.append({"task_id": str(task_id), "error": TASK_CANCELLED_MSG})
            continue

        previous_percent = int(round(float(task.percent_complete)))
        new_status = _derive_status(percent_complete)
        status_changed = new_status != task.status

        task.percent_complete = float(percent_complete)
        task.status = new_status

        progress_update = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=report_date,
            previous_percent_complete=previous_percent,
            percent_complete=percent_complete,
            notes=comment,
            updated_by=user_id,
        )
        db.session.add(progress_update)

        success_item = {
            "task_id": str(task.id),
            "task_name": task.name,
            "previous_percent_complete": previous_percent,
            "new_percent_complete": percent_complete,
            "status_changed": status_changed,
        }
        if status_changed:
            success_item["new_status"] = new_status
        success_items.append(success_item)
        updated_task_ids.add(task.id)

    return success_items, error_items, updated_task_ids


class ProjectProgressResource(Resource):
    """Resource for bulk progress updates."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.request_schema = ProgressUpdateRequestSchema()
        self.response_schema = ProgressUpdateResponseSchema()

    @require_jwt_auth
    @access_required(Operation.UPDATE, "progress")
    @limiter.limit("10 per minute", key_func=rate_limit_user_key)
    def post(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Bulk update task progress for a project."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_uuid_or_error()
        if company_error:
            return company_error

        user_id, user_error = _get_user_uuid_or_error()
        if user_error:
            return user_error

        assert company_id is not None
        assert user_id is not None

        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None

        if not request.is_json:
            return error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return error_response(INVALID_JSON_BODY_MSG, 400, error=BAD_REQUEST_ERROR)

        try:
            loaded = cast("ProgressPayload", self.request_schema.load(payload))
        except ValidationError as err:
            return error_response(
                VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR, errors=err.messages
            )

        report_date = _normalize_datetime(cast("datetime", loaded["date"]))
        updates = cast("list[dict[str, Any]]", loaded["updates"])

        task_ids = [item["task_id"] for item in updates]
        tasks = (
            Task.query.filter(Task.project_id == project.id)
            .filter(Task.id.in_(task_ids))
            .all()
        )
        task_map = {task.id: task for task in tasks}

        success_items, error_items, updated_task_ids = _process_progress_updates(
            updates, task_map, project, report_date, user_id
        )

        if success_items:
            _rollup_summary_tasks(updated_task_ids)

        try:
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return error_response(
                f"Database integrity error: {str(err.orig)}",
                409,
                error="Conflict",
            )

        updated_count = len(success_items)
        failed_count = len(error_items)

        if updated_count == 0 and error_items:
            if any(
                item["error"] in {TASK_COMPLETED_MSG, TASK_CANCELLED_MSG}
                for item in error_items
            ):
                return error_response(
                    TASK_COMPLETED_MSG,
                    422,
                    error=UNPROCESSABLE_ENTITY_ERROR,
                    errors=error_items,
                )
            if any(item["error"] == TASK_NOT_FOUND_MSG for item in error_items):
                return error_response(
                    TASK_NOT_FOUND_MSG,
                    404,
                    error=NOT_FOUND_ERROR,
                    errors=error_items,
                )

        response_payload = {
            "data": {
                "project_id": str(project.id),
                "date": report_date,
                "updated_count": updated_count,
                "failed_count": failed_count,
                "updates": success_items,
                "errors": error_items,
            },
            "message": PROGRESS_UPDATED_MSG,
        }

        return cast("ProgressPayload", self.response_schema.dump(response_payload)), 200


class ProjectProgressHistoryResource(Resource):
    """Resource for project progress history retrieval."""

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.query_schema = ProgressHistoryQuerySchema()
        self.response_schema = ProgressHistoryResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "progress")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str, version: str | None = None) -> ResponseTuple:
        """Retrieve progress update history for a project."""
        version_error = validate_api_version_or_error_response(version)
        if version_error:
            return version_error

        company_id, company_error = _get_company_uuid_or_error()
        if company_error:
            return company_error

        assert company_id is not None

        project, project_error = _get_project_or_error(project_id, company_id)
        if project_error:
            return project_error

        assert project is not None

        try:
            query_params = cast("QueryParams", self.query_schema.load(request.args))
        except ValidationError as err:
            return error_response(
                VALIDATION_FAILED_MSG, 400, error=BAD_REQUEST_ERROR, errors=err.messages
            )

        task_id = query_params.get("task_id")
        start_date = query_params.get("start_date")
        end_date = query_params.get("end_date")
        page = query_params.get("page", 1)
        per_page = query_params.get("per_page", 20)
        sort_order = query_params.get("sort_order", "desc")

        query = (
            db.session.query(ProgressUpdate, Task.name)
            .join(Task, ProgressUpdate.task_id == Task.id)
            .filter(ProgressUpdate.project_id == project.id)
        )

        if task_id:
            query = query.filter(ProgressUpdate.task_id == task_id)

        if start_date:
            query = query.filter(
                ProgressUpdate.update_date >= _normalize_datetime(start_date)
            )

        if end_date:
            query = query.filter(
                ProgressUpdate.update_date <= _normalize_datetime(end_date)
            )

        if sort_order == "asc":
            query = query.order_by(ProgressUpdate.update_date.asc())
        else:
            query = query.order_by(ProgressUpdate.update_date.desc())

        total = query.count()
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        rows = query.limit(per_page).offset((page - 1) * per_page).all()

        items = [_build_history_item(update, task_name) for update, task_name in rows]

        response_payload = {
            "data": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

        return cast("ProgressPayload", self.response_schema.dump(response_payload)), 200
