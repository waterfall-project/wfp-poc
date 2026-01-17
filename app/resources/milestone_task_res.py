# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Milestone-Task link endpoints.

Implements operations for linking tasks to milestones with automatic
target_date recalculation based on predecessor tasks.
"""

import uuid
from datetime import datetime
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.db import db
from app.models.milestone import Milestone
from app.models.milestone_task import MilestoneTask
from app.models.project import Project
from app.models.task import Task
from app.schemas.milestone_schema import (
    MilestoneTaskLinkSchema,
)
from app.services.guardian_service import Operation
from app.utils.api_version import validate_api_version
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    require_jwt_auth,
)
from app.utils.rate_limit import rate_limit_user_key

# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"
INVALID_MILESTONE_ID_MSG = "Invalid milestone_id"

ErrorResponse = tuple[dict[str, Any], int]

# Error Messages
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
MILESTONE_NOT_FOUND_MSG = "Milestone not found"
TASK_NOT_FOUND_MSG = "Task {task_id} not found or belongs to different project"
TASKS_CROSS_COMPANY_MSG = "All tasks must belong to the same company"
INVALID_COMPANY_ID_CLAIM_MSG = "Invalid token: company_id claim is not a valid UUID."

# Success Messages
TASKS_LINKED_MSG = "Tasks linked successfully, milestone target_date recalculated"
TASKS_SYNCED_MSG = "Milestone-task links synchronized successfully"


def _recalculate_milestone_target_date(milestone_id: uuid.UUID) -> datetime | None:
    """Recalculate milestone target_date as MAX(predecessor_tasks.planned_finish_date).

    Args:
        milestone_id: Milestone UUID.

    Returns:
        New target_date or None if no tasks linked.
    """
    # Get all linked tasks' planned_finish_date
    result = (
        db.session.query(func.max(Task.planned_finish_date))
        .join(MilestoneTask, MilestoneTask.task_id == Task.id)
        .filter(MilestoneTask.milestone_id == milestone_id)
        .scalar()
    )

    return result  # type: ignore[no-any-return]


def _parse_milestone_uuid(
    milestone_id: str,
) -> tuple[uuid.UUID | None, ErrorResponse | None]:
    """Parse milestone UUID or return a standardized error response."""
    try:
        return uuid.UUID(milestone_id), None
    except ValueError:
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_MILESTONE_ID_MSG},
            400,
        )


def _get_milestone_for_company(
    milestone_uuid: uuid.UUID, company_id: uuid.UUID
) -> tuple[Milestone | None, ErrorResponse | None]:
    """Retrieve milestone constrained to company or return 404."""
    milestone = (
        Milestone.query.join(Project, Milestone.project_id == Project.id)
        .filter(Milestone.id == milestone_uuid, Project.company_id == company_id)
        .first()
    )
    if not milestone:
        return None, (
            {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG},
            404,
        )
    return milestone, None


def _load_link_request_body() -> tuple[dict[str, Any] | None, ErrorResponse | None]:
    """Load and validate milestone-task link payload."""
    if not request.is_json:
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG},
            400,
        )

    raw_json = request.get_json(silent=True)
    if not isinstance(raw_json, dict):
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG},
            400,
        )

    try:
        schema = MilestoneTaskLinkSchema()
        data = cast("dict[str, Any]", schema.load(raw_json))
    except ValidationError as err:
        return None, (
            {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            },
            400,
        )

    if data is None:
        return None, (
            {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG},
            400,
        )

    return data, None


def _validate_tasks_for_milestone(
    task_ids: list[uuid.UUID], project_id: uuid.UUID
) -> tuple[list[Task] | None, ErrorResponse | None]:
    """Ensure tasks exist and belong to the milestone's project."""
    tasks = db.session.query(Task).filter(Task.id.in_(task_ids)).all()

    if len(tasks) != len(task_ids):
        found_ids = {task.id for task in tasks}
        missing_ids = set(task_ids) - found_ids
        missing_id = list(missing_ids)[0] if missing_ids else "unknown"
        return None, (
            {
                "error": NOT_FOUND_ERROR,
                "message": TASK_NOT_FOUND_MSG.format(task_id=missing_id),
            },
            404,
        )

    for task in tasks:
        if task.project_id != project_id:
            return None, (
                {
                    "error": UNPROCESSABLE_ENTITY_ERROR,
                    "message": TASK_NOT_FOUND_MSG.format(task_id=task.id),
                },
                422,
            )

    return tasks, None


def _build_predecessor_tasks(
    tasks: list[Task], include_wbs: bool = True
) -> list[dict[str, Any]]:
    """Serialize tasks for milestone predecessor response payloads."""
    serialized: list[dict[str, Any]] = []
    for task in tasks:
        item: dict[str, Any] = {
            "id": str(task.id),
            "name": task.name,
            "planned_finish_date": task.planned_finish_date.isoformat()
            if task.planned_finish_date
            else None,
            "is_critical": bool(task.is_critical)
            if task.is_critical is not None
            else False,
        }
        if include_wbs:
            item["wbs"] = task.wbs_code
            item["ms_project_uid"] = task.ms_project_uid
        serialized.append(item)
    return serialized


def _create_missing_links(milestone_uuid: uuid.UUID, task_ids: list[uuid.UUID]) -> int:
    """Create milestone-task links for missing associations and return count."""
    linked_count = 0
    for task_id in task_ids:
        existing = (
            db.session.query(MilestoneTask)
            .filter_by(milestone_id=milestone_uuid, task_id=task_id)
            .first()
        )
        if not existing:
            link = MilestoneTask()
            link.milestone_id = milestone_uuid
            link.task_id = task_id
            db.session.add(link)
            linked_count += 1
    return linked_count


def _sync_links(milestone_uuid: uuid.UUID, task_ids: list[uuid.UUID]) -> None:
    """Synchronize milestone-task links to match provided IDs."""
    current_links = (
        db.session.query(MilestoneTask).filter_by(milestone_id=milestone_uuid).all()
    )
    current_task_ids = {link.task_id for link in current_links}
    task_ids_set = set(task_ids)

    for link in current_links:
        if link.task_id not in task_ids_set:
            db.session.delete(link)

    for task_id in task_ids:
        if task_id not in current_task_ids:
            link = MilestoneTask()
            link.milestone_id = milestone_uuid
            link.task_id = task_id
            db.session.add(link)


def _commit_or_rollback_on_error(err: IntegrityError) -> ErrorResponse:
    """Rollback transaction and build integrity error response."""
    db.session.rollback()
    return {
        "error": BAD_REQUEST_ERROR,
        "message": f"Database integrity error: {str(err.orig)}",
    }, 400


class MilestoneTasksResource(Resource):
    """Resource for milestone-task link operations.

    Handles:
    - POST /v0/milestones/{milestone_id}/tasks - Link tasks to milestone
    - GET /v0/milestones/{milestone_id}/tasks - Get milestone predecessor tasks
    """

    @require_jwt_auth
    @access_required(Operation.UPDATE, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def post(
        self, milestone_id: str, version: str | None = None
    ) -> tuple[dict[str, Any], int]:
        """Link tasks to milestone as predecessors.

        Automatically recalculates milestone target_date as MAX(tasks.planned_finish_date).

        Args:
            milestone_id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
            400: If validation fails.
            422: If tasks belong to different project/company.
        """
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        milestone_uuid, error = _parse_milestone_uuid(milestone_id)
        if error:
            return error

        assert milestone_uuid is not None

        milestone, error = _get_milestone_for_company(milestone_uuid, company_id)
        if error:
            return error

        assert milestone is not None

        data, error = _load_link_request_body()
        if error:
            return error

        assert data is not None

        task_ids = data["task_ids"]
        tasks, error = _validate_tasks_for_milestone(task_ids, milestone.project_id)
        if error:
            return error

        assert tasks is not None

        linked_count = _create_missing_links(milestone_uuid, task_ids)

        new_target_date = _recalculate_milestone_target_date(milestone_uuid)
        if new_target_date:
            milestone.target_date = new_target_date

        try:
            db.session.commit()
        except IntegrityError as err:
            return _commit_or_rollback_on_error(err)

        predecessor_tasks = _build_predecessor_tasks(tasks, include_wbs=False)

        response = {
            "data": {
                "milestone_id": str(milestone_uuid),
                "target_date": milestone.target_date.isoformat()
                if milestone.target_date
                else None,
                "linked_task_count": linked_count,
                "predecessor_tasks": predecessor_tasks,
            },
            "message": TASKS_LINKED_MSG,
        }

        return response, 200

    @require_jwt_auth
    @access_required(Operation.READ, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(
        self, milestone_id: str, version: str | None = None
    ) -> tuple[dict[str, Any], int]:
        """Get all predecessor tasks linked to a milestone.

        Args:
            milestone_id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
        """
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        milestone_uuid, error = _parse_milestone_uuid(milestone_id)
        if error:
            return error

        assert milestone_uuid is not None

        milestone, error = _get_milestone_for_company(milestone_uuid, company_id)
        if error:
            return error

        assert milestone is not None

        tasks = (
            db.session.query(Task)
            .join(MilestoneTask, MilestoneTask.task_id == Task.id)
            .filter(MilestoneTask.milestone_id == milestone_uuid)
            .all()
        )

        predecessor_tasks = _build_predecessor_tasks(tasks)

        response = {
            "data": {
                "milestone_id": str(milestone_uuid),
                "milestone_name": milestone.name,
                "target_date": milestone.target_date.isoformat()
                if milestone.target_date
                else None,
                "predecessor_tasks": predecessor_tasks,
            }
        }

        return response, 200


class MilestoneTasksSyncResource(Resource):
    """Resource for syncing milestone-task links.

    Handles:
    - PUT /v0/milestones/{milestone_id}/tasks/sync - Sync milestone-task links
    """

    @require_jwt_auth
    @access_required(Operation.UPDATE, "milestones")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def put(
        self, milestone_id: str, version: str | None = None
    ) -> tuple[dict[str, Any], int]:
        """Sync milestone-task links (upsert operation).

        Removes links not in task_ids, adds new links, preserves existing.
        Used during MS Project reimport to synchronize milestone dependencies.

        Args:
            milestone_id: Milestone UUID from path parameter.
            version: Optional API version from path (e.g. "v0", "v1").

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
            400: If validation fails.
            422: If tasks belong to different project/company.
        """
        version_error = validate_api_version(version)
        if version_error:
            return version_error

        try:
            company_id = uuid.UUID(str(get_current_company_id()))
        except (TypeError, ValueError):
            return {
                "error": "Unauthorized",
                "message": INVALID_COMPANY_ID_CLAIM_MSG,
            }, 401

        milestone_uuid, error = _parse_milestone_uuid(milestone_id)
        if error:
            return error

        assert milestone_uuid is not None

        milestone, error = _get_milestone_for_company(milestone_uuid, company_id)
        if error:
            return error

        assert milestone is not None

        data, error = _load_link_request_body()
        if error:
            return error

        assert data is not None

        task_ids = data["task_ids"]
        tasks, error = _validate_tasks_for_milestone(task_ids, milestone.project_id)
        if error:
            return error

        assert tasks is not None

        _sync_links(milestone_uuid, task_ids)

        new_target_date = _recalculate_milestone_target_date(milestone_uuid)
        if new_target_date:
            milestone.target_date = new_target_date

        try:
            db.session.commit()
        except IntegrityError as err:
            return _commit_or_rollback_on_error(err)

        predecessor_tasks = _build_predecessor_tasks(tasks, include_wbs=False)

        response = {
            "data": {
                "milestone_id": str(milestone_uuid),
                "target_date": milestone.target_date.isoformat()
                if milestone.target_date
                else None,
                "linked_task_count": len(task_ids),
                "predecessor_tasks": predecessor_tasks,
            },
            "message": TASKS_SYNCED_MSG,
        }

        return response, 200
