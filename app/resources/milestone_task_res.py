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
from typing import Any

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
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    require_jwt_auth,
)

# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"

# Error Messages
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
MILESTONE_NOT_FOUND_MSG = "Milestone not found"
TASK_NOT_FOUND_MSG = "Task {task_id} not found or belongs to different project"
TASKS_CROSS_COMPANY_MSG = "All tasks must belong to the same company"

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

    return result


class MilestoneTasksResource(Resource):
    """Resource for milestone-task link operations.

    Handles:
    - POST /v0/milestones/{milestone_id}/tasks - Link tasks to milestone
    - GET /v0/milestones/{milestone_id}/tasks - Get milestone predecessor tasks
    """

    @require_jwt_auth
    @access_required(Operation.UPDATE)
    @limiter.limit("100 per minute")
    def post(self, milestone_id: str) -> tuple[dict[str, Any], int]:
        """Link tasks to milestone as predecessors.

        Automatically recalculates milestone target_date as MAX(tasks.planned_finish_date).

        Args:
            milestone_id: Milestone UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
            400: If validation fails.
            422: If tasks belong to different project/company.
        """
        company_id = get_current_company_id()

        try:
            milestone_uuid = uuid.UUID(milestone_id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid milestone_id",
            }, 400

        # Get milestone and verify company
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Get project to verify company
        project = db.session.get(Project, milestone.project_id)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Validate request body
        if not request.is_json:
            return {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG}, 400

        try:
            schema = MilestoneTaskLinkSchema()
            data = schema.load(request.json)
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        task_ids = [uuid.UUID(tid) for tid in data["task_ids"]]

        # Verify all tasks exist and belong to same project
        tasks = db.session.query(Task).filter(Task.id.in_(task_ids)).all()

        if len(tasks) != len(task_ids):
            found_ids = {task.id for task in tasks}
            missing_ids = set(task_ids) - found_ids
            return {
                "error": UNPROCESSABLE_ENTITY_ERROR,
                "message": TASK_NOT_FOUND_MSG.format(task_id=list(missing_ids)[0]),
            }, 422

        # Verify all tasks belong to same project
        for task in tasks:
            if task.project_id != milestone.project_id:
                return {
                    "error": UNPROCESSABLE_ENTITY_ERROR,
                    "message": TASK_NOT_FOUND_MSG.format(task_id=task.id),
                }, 422

        # Create milestone-task links (skip duplicates)
        linked_count = 0
        for task_id in task_ids:
            # Check if link already exists
            existing = (
                db.session.query(MilestoneTask)
                .filter_by(milestone_id=milestone_uuid, task_id=task_id)
                .first()
            )

            if not existing:
                link = MilestoneTask(milestone_id=milestone_uuid, task_id=task_id)
                db.session.add(link)
                linked_count += 1

        # Recalculate milestone target_date
        new_target_date = _recalculate_milestone_target_date(milestone_uuid)
        if new_target_date:
            milestone.target_date = new_target_date

        try:
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return {
                "error": BAD_REQUEST_ERROR,
                "message": f"Database integrity error: {str(err.orig)}",
            }, 400

        # Build response with predecessor task details
        predecessor_tasks = []
        for task in tasks:
            predecessor_tasks.append(
                {
                    "id": str(task.id),
                    "name": task.name,
                    "planned_finish_date": task.planned_finish_date.isoformat()
                    if task.planned_finish_date
                    else None,
                    "is_critical": task.is_critical or False,
                }
            )

        response = {
            "data": {
                "milestone_id": str(milestone_uuid),
                "target_date": milestone.target_date.isoformat()
                if milestone.target_date
                else None,
                "linked_task_count": len(task_ids),
                "predecessor_tasks": predecessor_tasks,
            },
            "message": TASKS_LINKED_MSG,
        }

        return response, 200

    @require_jwt_auth
    @access_required(Operation.READ)
    @limiter.limit("100 per minute")
    def get(self, milestone_id: str) -> tuple[dict[str, Any], int]:
        """Get all predecessor tasks linked to a milestone.

        Args:
            milestone_id: Milestone UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
        """
        company_id = get_current_company_id()

        try:
            milestone_uuid = uuid.UUID(milestone_id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid milestone_id",
            }, 400

        # Get milestone and verify company
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Get project to verify company
        project = db.session.get(Project, milestone.project_id)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Get all linked tasks
        tasks = (
            db.session.query(Task)
            .join(MilestoneTask, MilestoneTask.task_id == Task.id)
            .filter(MilestoneTask.milestone_id == milestone_uuid)
            .all()
        )

        predecessor_tasks = []
        for task in tasks:
            predecessor_tasks.append(
                {
                    "id": str(task.id),
                    "name": task.name,
                    "wbs": task.wbs_code,
                    "planned_finish_date": task.planned_finish_date.isoformat()
                    if task.planned_finish_date
                    else None,
                    "is_critical": task.is_critical or False,
                    "ms_project_uid": task.ms_project_uid,
                }
            )

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
    @access_required(Operation.UPDATE)
    @limiter.limit("100 per minute")
    def put(self, milestone_id: str) -> tuple[dict[str, Any], int]:
        """Sync milestone-task links (upsert operation).

        Removes links not in task_ids, adds new links, preserves existing.
        Used during MS Project reimport to synchronize milestone dependencies.

        Args:
            milestone_id: Milestone UUID from path parameter.

        Returns:
            Tuple of (response_dict, status_code).

        Raises:
            404: If milestone not found or wrong company.
            400: If validation fails.
            422: If tasks belong to different project/company.
        """
        company_id = get_current_company_id()

        try:
            milestone_uuid = uuid.UUID(milestone_id)
        except ValueError:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": "Invalid milestone_id",
            }, 400

        # Get milestone and verify company
        milestone = db.session.get(Milestone, milestone_uuid)
        if not milestone:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Get project to verify company
        project = db.session.get(Project, milestone.project_id)
        if not project or project.company_id != company_id:
            return {"error": NOT_FOUND_ERROR, "message": MILESTONE_NOT_FOUND_MSG}, 404

        # Validate request body
        if not request.is_json:
            return {"error": BAD_REQUEST_ERROR, "message": INVALID_JSON_BODY_MSG}, 400

        try:
            schema = MilestoneTaskLinkSchema()
            data = schema.load(request.json)
        except ValidationError as err:
            return {
                "error": BAD_REQUEST_ERROR,
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 400

        task_ids = [uuid.UUID(tid) for tid in data["task_ids"]]

        # Verify all tasks exist and belong to same project
        tasks = db.session.query(Task).filter(Task.id.in_(task_ids)).all()

        if len(tasks) != len(task_ids):
            found_ids = {task.id for task in tasks}
            missing_ids = set(task_ids) - found_ids
            return {
                "error": UNPROCESSABLE_ENTITY_ERROR,
                "message": TASK_NOT_FOUND_MSG.format(task_id=list(missing_ids)[0]),
            }, 422

        # Verify all tasks belong to same project
        for task in tasks:
            if task.project_id != milestone.project_id:
                return {
                    "error": UNPROCESSABLE_ENTITY_ERROR,
                    "message": TASK_NOT_FOUND_MSG.format(task_id=task.id),
                }, 422

        # Get current links
        current_links = (
            db.session.query(MilestoneTask).filter_by(milestone_id=milestone_uuid).all()
        )
        current_task_ids = {link.task_id for link in current_links}

        # Remove links not in new task_ids
        task_ids_set = set(task_ids)
        for link in current_links:
            if link.task_id not in task_ids_set:
                db.session.delete(link)

        # Add new links
        for task_id in task_ids:
            if task_id not in current_task_ids:
                link = MilestoneTask(milestone_id=milestone_uuid, task_id=task_id)
                db.session.add(link)

        # Recalculate milestone target_date
        new_target_date = _recalculate_milestone_target_date(milestone_uuid)
        if new_target_date:
            milestone.target_date = new_target_date

        try:
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return {
                "error": BAD_REQUEST_ERROR,
                "message": f"Database integrity error: {str(err.orig)}",
            }, 400

        # Build response with predecessor task details
        predecessor_tasks = []
        for task in tasks:
            predecessor_tasks.append(
                {
                    "id": str(task.id),
                    "name": task.name,
                    "planned_finish_date": task.planned_finish_date.isoformat()
                    if task.planned_finish_date
                    else None,
                    "is_critical": task.is_critical or False,
                }
            )

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
