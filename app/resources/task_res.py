# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask-RESTful resources for Task endpoints.

Implements CRUD operations for tasks with proper authentication,
authorization, validation, pagination, and predecessor management.
"""

import math
import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

from flask import request
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models.db import db
from app.models.project import Project
from app.models.task import Task
from app.models.task_predecessor import TaskPredecessor
from app.schemas.task_schema import (
    TaskBulkCreateSchema,
    TaskBulkResponseSchema,
    TaskCreateSchema,
    TaskListSchema,
    TaskResponseSchema,
    TaskSchema,
    TaskSyncResponseSchema,
    TaskSyncSchema,
    TaskUpdateSchema,
)
from app.services.guardian_service import Operation
from app.utils.jwt_decorators import (
    access_required,
    get_current_company_id,
    get_current_user_id,
    require_jwt_auth,
)


def _get_correlation_id() -> str:
    """Get or generate correlation ID for request tracing.

    Returns:
        Correlation ID from header or newly generated UUID.
    """
    return request.headers.get("X-Correlation-ID", str(uuid.uuid4()))


# HTTP Error Types
BAD_REQUEST_ERROR = "Bad Request"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"

# Common Error Messages
INVALID_PROJECT_ID_MSG = "Invalid project_id format"
INVALID_UUID_MSG = "Invalid UUID format"
INVALID_PAGINATION_MSG = "Invalid pagination parameters"
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
DATABASE_INTEGRITY_ERROR_MSG = "Database integrity error"

# Task-specific Error Messages
PROJECT_NOT_FOUND_MSG = "Project not found"
TASK_NOT_FOUND_MSG = "Task not found"
INVALID_STATUS_MSG = "Invalid status: {status}"
INVALID_SORT_BY_MSG = "Invalid sort_by: {sort_by}"
INVALID_SORT_ORDER_MSG = "Invalid sort_order: {sort_order}"
CIRCULAR_DEPENDENCY_MSG = "Circular dependency detected in task predecessors"
REFERENCED_TASK_MSG = "Cannot delete task: it is referenced as a predecessor"
BULK_LIMIT_EXCEEDED_MSG = "Bulk operation limited to 500 tasks per request"

# Success Messages
TASK_CREATED_MSG = "Task created successfully"
TASK_UPDATED_MSG = "Task updated successfully"
TASK_DELETED_MSG = "Task deleted successfully"


def _normalize_datetime(value: datetime | date | None) -> datetime | None:
    """Normalize datetime to naive UTC or convert date to datetime.

    Datetimes are converted to naive UTC.
    Date objects are converted to datetime at midnight UTC.

    Args:
        value: Datetime or date value to normalize.

    Returns:
        Naive UTC datetime or None.
    """
    if value is None:
        return None
    # If it's a date (not datetime), convert to datetime at midnight
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time())
    # If it's a datetime, normalize to naive UTC
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _rate_limit_user_key() -> str:
    """Rate limiting key based on authenticated user.

    Falls back to remote address when user_id is absent.
    """
    user_id = get_current_user_id()
    if user_id:
        return str(user_id)
    return request.remote_addr or "anonymous"


def _validate_predecessors_in_project(
    predecessors: list[dict[str, Any]], project_id: uuid.UUID
) -> tuple[bool, str | None]:
    """Validate all predecessor tasks belong to the same project.

    Args:
        predecessors: List of predecessor relationships with predecessor_task_id.
        project_id: Expected project UUID.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not predecessors:
        return True, None

    for pred in predecessors:
        pred_id = uuid.UUID(str(pred["predecessor_task_id"]))
        pred_task = Task.query.filter_by(id=pred_id, project_id=project_id).first()
        if not pred_task:
            return (
                False,
                f"Predecessor task {pred_id} not found in project {project_id}",
            )

    return True, None


def _parse_boolean_param(value: str | None) -> bool | None:
    """Parse boolean query parameter strictly.

    Args:
        value: Query parameter value.

    Returns:
        True, False, or None if parameter not provided.

    Raises:
        ValueError: If value is not a valid boolean representation.
    """
    if value is None:
        return None

    lower_value = value.lower()
    if lower_value in ("true", "1", "yes"):
        return True
    if lower_value in ("false", "0", "no"):
        return False

    raise ValueError(f"Invalid boolean value: {value}")


def _get_task_type(is_milestone: bool | None, is_summary: bool | None) -> str:
    """Determine task type from boolean flags.

    Args:
        is_milestone: Whether task is a milestone.
        is_summary: Whether task is a summary.

    Returns:
        Task type string (milestone, summary, or task).
    """
    if is_milestone:
        return "milestone"
    if is_summary:
        return "summary"
    return "task"


def _detect_circular_dependency(
    task_id: uuid.UUID, predecessors: list[dict[str, Any]], project_id: uuid.UUID
) -> bool:
    """Detect circular dependencies in predecessor graph.

    Uses depth-first search to detect cycles in the task dependency graph.

    Args:
        task_id: The task being checked.
        predecessors: List of predecessor relationships to add.
        project_id: Project context for scoping query.

    Returns:
        True if a circular dependency is detected, False otherwise.
    """
    if not predecessors:
        return False

    # Build adjacency map from database
    existing_preds = (
        TaskPredecessor.query.join(Task, TaskPredecessor.successor_id == Task.id)
        .filter(Task.project_id == project_id)
        .all()
    )

    graph: dict[uuid.UUID, list[uuid.UUID]] = {}
    for pred in existing_preds:
        if pred.successor_id not in graph:
            graph[pred.successor_id] = []
        graph[pred.successor_id].append(pred.predecessor_id)

    # Add new relationships
    if task_id not in graph:
        graph[task_id] = []
    for pred in predecessors:
        pred_id = uuid.UUID(str(pred["predecessor_task_id"]))
        if pred_id not in graph[task_id]:
            graph[task_id].append(pred_id)

    # DFS to detect cycle
    visited: set[uuid.UUID] = set()
    recursion_stack: set[uuid.UUID] = set()

    def has_cycle(node: uuid.UUID) -> bool:
        visited.add(node)
        recursion_stack.add(node)

        # Check all neighbors
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in recursion_stack:
                return True

        recursion_stack.remove(node)
        return False

    # Start DFS from the task being modified
    return has_cycle(task_id)


class TaskListResource(Resource):
    """REST resource for task collection operations.

    Handles /v0/projects/{project_id}/tasks endpoint for listing and creating tasks.
    """

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.task_schema = TaskSchema()
        self.response_schema = TaskResponseSchema()
        self.list_schema = TaskListSchema()
        self.create_schema = TaskCreateSchema()

    @require_jwt_auth
    @access_required(Operation.LIST, "tasks")
    @limiter.limit("100 per minute", key_func=_rate_limit_user_key)
    def get(self, project_id: str) -> tuple[dict, int]:
        """Retrieve paginated list of tasks for a project.

        Query Parameters:
            page (int): Page number (default: 1, min: 1)
            per_page (int): Items per page (default: 20, min: 1, max: 100)
            parent_id (uuid|"null"): Filter by parent task (null for top-level)
            is_milestone (bool): Filter milestones only
            is_summary (bool): Filter summary tasks only
            is_critical (bool): Filter critical path tasks only
            status (str): Filter by status
                (not_started, in_progress, completed, cancelled)
            search (str): Search in name field
            sort_by (str): Field to sort by (wbs, name, start, finish)
            sort_order (str): Sort direction (asc, desc)

        Args:
            project_id: Project UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Successful response with paginated task list
                - 400: Invalid query parameters
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Project not found

        Examples:
            >>> GET /v0/projects/{uuid}/tasks?page=1&per_page=20&is_milestone=true
            {
                "data": [...],
                "page": 1,
                "per_page": 20,
                "total": 50,
                "total_pages": 3
            }
        """
        company_id = get_current_company_id()

        # Validate project exists and belongs to company
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {
                "message": "Invalid project_id format",
                "errors": {"validation": "Invalid request"},
            }, 400

        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Parse and validate pagination parameters
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return {
                "message": INVALID_PAGINATION_MSG,
            }, 400

        # Build base query filtered by project
        query = Task.query.filter_by(project_id=project_uuid)

        # Apply parent_id filter
        parent_id_param = request.args.get("parent_id")
        if parent_id_param:
            if parent_id_param.lower() == "null":
                query = query.filter(Task.parent_id.is_(None))
            else:
                try:
                    parent_uuid = uuid.UUID(parent_id_param)
                    query = query.filter_by(parent_id=parent_uuid)
                except ValueError:
                    return {
                        "message": "Invalid UUID format",
                        "errors": {"validation": "Invalid request"},
                    }, 400

        # Apply boolean filters with strict validation
        try:
            is_milestone = _parse_boolean_param(request.args.get("is_milestone"))
            if is_milestone is not None and is_milestone:
                query = query.filter_by(type="milestone")

            is_summary = _parse_boolean_param(request.args.get("is_summary"))
            if is_summary is not None and is_summary:
                query = query.filter_by(type="summary")

            is_critical = _parse_boolean_param(request.args.get("is_critical"))
            if is_critical is not None:
                query = query.filter_by(is_critical=is_critical)
        except ValueError as e:
            return {
                "message": "Invalid boolean parameter",
                "errors": {"query_params": str(e)},
            }, 400

        # Apply status filter
        status = request.args.get("status")
        if status:
            if status not in ["not_started", "in_progress", "completed", "cancelled"]:
                return {
                    "message": INVALID_STATUS_MSG.format(status=status),
                }, 400
            query = query.filter_by(status=status)

        # Apply search filter
        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(Task.name.ilike(search_pattern))

        # Apply sorting
        sort_by = request.args.get("sort_by", "wbs")
        sort_order = request.args.get("sort_order", "asc")

        if sort_by not in ["wbs", "name", "start", "finish"]:
            return {
                "message": INVALID_SORT_BY_MSG.format(sort_by=sort_by),
            }, 400

        if sort_order not in ["asc", "desc"]:
            return {
                "message": INVALID_SORT_ORDER_MSG.format(sort_order=sort_order),
            }, 400

        # Map sort_by to model fields
        sort_field_map = {
            "wbs": Task.wbs_code,
            "name": Task.name,
            "start": Task.planned_start_date,
            "finish": Task.planned_finish_date,
        }

        sort_field = sort_field_map[sort_by]
        if sort_order == "desc":
            sort_field = sort_field.desc()  # type: ignore[assignment]

        query = query.order_by(sort_field)

        # Execute paginated query
        total = query.count()
        total_pages = math.ceil(total / per_page)

        tasks = query.offset((page - 1) * per_page).limit(per_page).all()

        # Serialize response
        response_data = {
            "data": [self.task_schema.dump(task) for task in tasks],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.CREATE, "tasks")
    @limiter.limit("30 per minute", key_func=_rate_limit_user_key)
    def post(self, project_id: str) -> tuple[dict, int]:
        """Create a new task within a project.

        Args:
            project_id: Project UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 201: Task created successfully
                - 400: Invalid request data
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Project not found
                - 409: Circular dependency in predecessors
                - 422: Unprocessable entity (validation error)

        Examples:
            >>> POST /v0/projects/{uuid}/tasks
            {
                "name": "Design Phase",
                "start": "2026-02-01T09:00:00Z",
                "finish": "2026-02-15T18:00:00Z"
            }
        """
        company_id = get_current_company_id()

        # Validate project exists and belongs to company
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {
                "message": "Invalid project_id format",
                "errors": {"validation": "Invalid request"},
            }, 400

        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Validate request body
        if not request.is_json:
            return {
                "message": INVALID_JSON_BODY_MSG,
                "errors": {"body": "Request body must be JSON"},
            }, 400

        json_data_raw = request.get_json()

        if not isinstance(json_data_raw, dict):
            return {
                "message": INVALID_JSON_BODY_MSG,
                "errors": {"body": "Request body must be a JSON object"},
            }, 400

        json_data = cast("dict[str, Any]", json_data_raw)

        # Validate schema
        try:
            validated_data: dict[str, Any] = cast(
                "dict[str, Any]", self.create_schema.load(json_data)
            )
        except ValidationError as err:
            return {
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 422

        # Validate predecessors belong to same project
        predecessors = validated_data.get("predecessors", [])
        is_valid, error_msg = _validate_predecessors_in_project(
            predecessors, project_uuid
        )
        if not is_valid:
            return {
                "message": "Invalid predecessor reference",
                "errors": {"predecessors": error_msg},
            }, 400

        # Note: Circular dependency check is deferred to PATCH/update
        # where the task ID is known. For POST, we allow creation and
        # rely on validation during subsequent updates.

        # Create task
        task_type = _get_task_type(
            validated_data.get("is_milestone"), validated_data.get("is_summary")
        )

        task = Task()
        task.project_id = project_uuid
        task.name = validated_data["name"]
        task.wbs_code = validated_data.get("wbs")
        task.planned_start_date = _normalize_datetime(validated_data["start"])
        task.planned_finish_date = _normalize_datetime(validated_data["finish"])
        task.status = validated_data.get("status", "not_started")
        task.percent_complete = validated_data.get("percent_complete", 0)
        task.ms_project_uid = validated_data.get("ms_project_uid")
        task.type = task_type
        task.parent_id = validated_data.get("parent_id")

        try:
            db.session.add(task)
            db.session.flush()

            # Add predecessors
            for pred in predecessors:
                predecessor_rel = TaskPredecessor()
                predecessor_rel.successor_id = task.id
                predecessor_rel.predecessor_id = uuid.UUID(
                    str(pred["predecessor_task_id"])
                )
                predecessor_rel.type = pred["type"]
                predecessor_rel.lag_minutes = pred.get("lag", 0)
                db.session.add(predecessor_rel)

            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return {
                "message": "Database integrity error",
                "errors": {
                    "database": str(e.orig) if hasattr(e, "orig") else str(e),
                },
            }, 409

        # Serialize response
        response_data = {
            "data": self.task_schema.dump(task),
            "message": TASK_CREATED_MSG,
        }

        return response_data, 201


class TaskResource(Resource):
    """REST resource for individual task operations.

    Handles /v0/projects/{project_id}/tasks/{id} endpoint for
    retrieve, update and delete operations.
    """

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.task_schema = TaskSchema()
        self.response_schema = TaskResponseSchema()
        self.update_schema = TaskUpdateSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "tasks")
    @limiter.limit("200 per minute", key_func=_rate_limit_user_key)
    def get(self, project_id: str, id: str) -> tuple[dict, int]:
        """Retrieve a specific task by ID.

        Args:
            project_id: Project UUID.
            id: Task UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Successful response with task details
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Task or project not found

        Examples:
            >>> GET /v0/projects/{project_uuid}/tasks/{task_uuid}
            {
                "data": {...},
                "message": null
            }
        """
        company_id = get_current_company_id()

        # Validate UUIDs
        try:
            project_uuid = uuid.UUID(project_id)
            task_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "message": "Invalid UUID format",
                "errors": {"validation": "Invalid request"},
            }, 400

        # Validate project exists and belongs to company
        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Retrieve task
        task = Task.query.filter_by(id=task_uuid, project_id=project_uuid).first()
        if not task:
            return {
                "message": TASK_NOT_FOUND_MSG,
            }, 404

        # Serialize response
        response_data = {
            "data": self.task_schema.dump(task),
        }

        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.UPDATE, "tasks")
    @limiter.limit("50 per minute", key_func=_rate_limit_user_key)
    def patch(
        self, project_id: str, id: str
    ) -> tuple[dict, int] | tuple[dict, int, dict[str, str]]:
        """Update a task (partial update).

        Args:
            project_id: Project UUID.
            id: Task UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Task updated successfully
                - 400: Invalid request data
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Task or project not found
                - 409: Circular dependency in predecessors
                - 422: Unprocessable entity (validation error)

        Examples:
            >>> PATCH /v0/projects/{project_uuid}/tasks/{task_uuid}
            {
                "status": "in_progress",
                "percent_complete": 25
            }
        """
        company_id = get_current_company_id()

        # Validate UUIDs
        try:
            project_uuid = uuid.UUID(project_id)
            task_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "message": "Invalid UUID format",
                "errors": {"validation": "Invalid request"},
            }, 400

        # Validate project exists and belongs to company
        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Retrieve task
        task = Task.query.filter_by(id=task_uuid, project_id=project_uuid).first()
        if not task:
            return {
                "message": TASK_NOT_FOUND_MSG,
            }, 404

        # Validate request body
        if not request.is_json:
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data_raw = request.get_json()

        if not isinstance(json_data_raw, dict):
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data = cast("dict[str, Any]", json_data_raw)

        # Validate schema
        try:
            validated_data: dict[str, Any] = cast(
                "dict[str, Any]", self.update_schema.load(json_data)
            )
        except ValidationError as err:
            return {
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 422

        # Check for circular dependencies if predecessors are being updated
        predecessors = validated_data.get("predecessors")
        if predecessors is not None:
            # Validate predecessors belong to same project
            is_valid, error_msg = _validate_predecessors_in_project(
                predecessors, project_uuid
            )
            if not is_valid:
                return {
                    "message": "Invalid predecessor reference",
                    "errors": {"predecessors": error_msg},
                }, 400

            # Check for circular dependencies
            if _detect_circular_dependency(task_uuid, predecessors, project_uuid):
                correlation_id = _get_correlation_id()
                return (
                    {
                        "message": CIRCULAR_DEPENDENCY_MSG,
                        "errors": {"predecessors": "Circular dependency detected"},
                        "correlation_id": correlation_id,
                    },
                    409,
                    {"X-Correlation-ID": correlation_id},
                )

        # Update task fields
        if "name" in validated_data:
            task.name = validated_data["name"]
        if "ms_project_uid" in validated_data:
            task.ms_project_uid = validated_data["ms_project_uid"]
        if "start" in validated_data:
            task.planned_start_date = _normalize_datetime(validated_data["start"])
        if "finish" in validated_data:
            task.planned_finish_date = _normalize_datetime(validated_data["finish"])
        if "status" in validated_data:
            task.status = validated_data["status"]
        if "percent_complete" in validated_data:
            task.percent_complete = validated_data["percent_complete"]
        if "actual_start" in validated_data:
            task.actual_start_date = _normalize_datetime(validated_data["actual_start"])
        if "actual_finish" in validated_data:
            task.actual_finish_date = _normalize_datetime(
                validated_data["actual_finish"]
            )
        if "remaining_cost" in validated_data:
            task.remaining_cost = validated_data["remaining_cost"]

        # Update predecessors if provided
        if predecessors is not None:
            # Remove existing predecessors
            TaskPredecessor.query.filter_by(successor_id=task_uuid).delete()

            # Add new predecessors
            for pred in predecessors:
                predecessor_rel = TaskPredecessor()
                predecessor_rel.successor_id = task_uuid
                predecessor_rel.predecessor_id = uuid.UUID(
                    str(pred["predecessor_task_id"])
                )
                predecessor_rel.type = pred["type"]
                predecessor_rel.lag_minutes = pred.get("lag", 0)
                db.session.add(predecessor_rel)

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return {
                "message": "Database integrity error",
                "errors": {
                    "database": str(e.orig) if hasattr(e, "orig") else str(e),
                },
            }, 409

        # Refresh to get updated relationships
        db.session.refresh(task)

        # Serialize response
        response_data = {
            "data": self.task_schema.dump(task),
            "message": TASK_UPDATED_MSG,
        }

        return response_data, 200

    @require_jwt_auth
    @access_required(Operation.DELETE, "tasks")
    @limiter.limit("20 per minute", key_func=_rate_limit_user_key)
    def delete(
        self, project_id: str, id: str
    ) -> tuple[dict | str, int] | tuple[dict, int, dict[str, str]]:
        """Delete a task.

        Cascades to assignments and child tasks. Blocks if task is
        referenced as a predecessor by other tasks.

        Args:
            project_id: Project UUID.
            id: Task UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 204: Task deleted successfully
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Task or project not found
                - 409: Task is referenced as predecessor

        Examples:
            >>> DELETE /v0/projects/{project_uuid}/tasks/{task_uuid}
            204 No Content
        """
        company_id = get_current_company_id()

        # Validate UUIDs
        try:
            project_uuid = uuid.UUID(project_id)
            task_uuid = uuid.UUID(id)
        except ValueError:
            return {
                "message": "Invalid UUID format",
                "errors": {"validation": "Invalid request"},
            }, 400

        # Validate project exists and belongs to company
        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Retrieve task
        task = Task.query.filter_by(id=task_uuid, project_id=project_uuid).first()
        if not task:
            return {
                "message": TASK_NOT_FOUND_MSG,
            }, 404

        # Check if task is referenced as predecessor by tasks in the same project
        successor_count = (
            TaskPredecessor.query.join(Task, TaskPredecessor.successor_id == Task.id)
            .filter(
                TaskPredecessor.predecessor_id == task_uuid,
                Task.project_id == project_uuid,
            )
            .count()
        )
        if successor_count > 0:
            correlation_id = _get_correlation_id()
            return (
                {
                    "message": REFERENCED_TASK_MSG,
                    "errors": {"predecessor": "Task is referenced by other tasks"},
                    "correlation_id": correlation_id,
                },
                409,
                {"X-Correlation-ID": correlation_id},
            )

        # Delete task (cascade will handle children and assignments)
        try:
            db.session.delete(task)
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return {
                "message": "Database integrity error",
                "errors": {"database": str(e.orig) if hasattr(e, "orig") else str(e)},
            }, 409

        return "", 204


class TaskBulkResource(Resource):
    """REST resource for bulk task operations.

    Handles /v0/projects/{project_id}/tasks/bulk endpoint for
    efficient batch creation.
    """

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.task_schema = TaskSchema()
        self.bulk_create_schema = TaskBulkCreateSchema()
        self.bulk_response_schema = TaskBulkResponseSchema()

    @require_jwt_auth
    @access_required(Operation.CREATE, "tasks")
    @limiter.limit("10 per minute", key_func=_rate_limit_user_key)
    def post(self, project_id: str) -> tuple[dict, int]:
        """Bulk create tasks for a project.

        Allows partial success - returns created tasks and errors for failed items.

        Args:
            project_id: Project UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 201: Tasks created (may include partial failures)
                - 400: Invalid request data
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Project not found
                - 429: Rate limit exceeded

        Examples:
            >>> POST /v0/projects/{uuid}/tasks/bulk
            {
                "tasks": [
                    {"name": "Task 1", "start": "...", "finish": "..."},
                    {"name": "Task 2", "start": "...", "finish": "..."}
                ]
            }
        """
        company_id = get_current_company_id()

        # Validate project exists and belongs to company
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {
                "message": "Invalid project_id format",
                "errors": {"validation": "Invalid request"},
            }, 400

        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Validate request body
        if not request.is_json:
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data_raw = request.get_json()

        if not isinstance(json_data_raw, dict):
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data = cast("dict[str, Any]", json_data_raw)

        # Validate bulk schema
        try:
            validated_data_raw = self.bulk_create_schema.load(json_data)
            validated_data = cast("dict[str, Any]", validated_data_raw)
        except ValidationError as err:
            return {
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 422

        tasks_data = validated_data["tasks"]
        created_tasks = []
        errors = []

        # Process each task
        for idx, task_data in enumerate(tasks_data):
            try:
                # Get predecessors
                predecessors = task_data.get("predecessors", [])

                # Validate predecessors (skip validation errors in bulk, just log them)
                # This allows partial success

                # Create task
                task_type = _get_task_type(
                    task_data.get("is_milestone"), task_data.get("is_summary")
                )

                task = Task()
                task.project_id = project_uuid
                task.name = task_data["name"]
                task.wbs_code = task_data.get("wbs")
                task.planned_start_date = _normalize_datetime(task_data["start"])
                task.planned_finish_date = _normalize_datetime(task_data["finish"])
                task.status = task_data.get("status", "not_started")
                task.percent_complete = task_data.get("percent_complete", 0)
                task.ms_project_uid = task_data.get("ms_project_uid")
                task.type = task_type
                task.parent_id = task_data.get("parent_id")

                db.session.add(task)
                db.session.flush()

                # Add predecessors (validate they exist in same project)
                invalid_predecessors = []
                for pred in predecessors:
                    pred_id = uuid.UUID(str(pred["predecessor_task_id"]))
                    # Check predecessor exists in same project
                    pred_task = Task.query.filter_by(
                        id=pred_id, project_id=project_uuid
                    ).first()
                    if not pred_task:
                        invalid_predecessors.append(str(pred_id))
                        continue  # Skip invalid predecessor in bulk operation

                    predecessor_rel = TaskPredecessor()
                    predecessor_rel.successor_id = task.id
                    predecessor_rel.predecessor_id = pred_id
                    predecessor_rel.type = pred["type"]
                    predecessor_rel.lag_minutes = pred.get("lag", 0)
                    db.session.add(predecessor_rel)

                if invalid_predecessors:
                    errors.append(
                        {
                            "index": idx,
                            "task_name": task_data.get("name", "unknown"),
                            "errors": {
                                "predecessors": f"Invalid predecessor IDs: {', '.join(invalid_predecessors)}"
                            },
                        }
                    )

                created_tasks.append(task)

            except Exception as e:
                errors.append(
                    {
                        "index": idx,
                        "task_name": task_data.get("name", "unknown"),
                        "errors": {"detail": str(e)},
                    }
                )

        # Commit all successful tasks
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return {
                "message": "Database integrity error",
                "errors": {
                    "database": str(e.orig) if hasattr(e, "orig") else str(e),
                },
            }, 409

        # Prepare response
        created_count = len(created_tasks)
        failed_count = len(errors)

        response_data = {
            "data": {
                "created_count": created_count,
                "failed_count": failed_count,
                "tasks": [self.task_schema.dump(task) for task in created_tasks],
                "errors": errors,
            },
            "message": f"{created_count} tasks created, {failed_count} failed",
        }

        return response_data, 201


class TaskSyncResource(Resource):
    """REST resource for task synchronization (upsert).

    Handles /v0/projects/{project_id}/tasks/sync endpoint for
    MS Project reimport reconciliation.
    """

    def __init__(self) -> None:
        """Initialize schemas for reuse."""
        self.task_schema = TaskSchema()
        self.sync_schema = TaskSyncSchema()
        self.sync_response_schema = TaskSyncResponseSchema()

    @require_jwt_auth
    @access_required(Operation.UPDATE, "tasks")
    @limiter.limit("10 per minute", key_func=_rate_limit_user_key)
    def put(self, project_id: str) -> tuple[dict, int]:
        """Sync tasks using ms_project_uid as reconciliation key.

        Updates existing tasks by ms_project_uid. Tasks not found are tracked
        in not_found_uids. Only planning fields are updated (dates, duration,
        predecessors). Tracking data (progress, actuals, RAE) is preserved.

        Args:
            project_id: Project UUID.

        Returns:
            Tuple of (response_dict, status_code):
                - 200: Tasks synchronized successfully
                - 400: Invalid request data
                - 401: Missing or invalid JWT
                - 403: Insufficient permissions
                - 404: Project not found
                - 422: Unprocessable entity (validation error)

        Examples:
            >>> PUT /v0/projects/{uuid}/tasks/sync
            {
                "tasks": [
                    {
                        "ms_project_uid": 42,
                        "name": "Updated Task",
                        "planned_start_date": "...",
                        "planned_finish_date": "..."
                    }
                ]
            }
        """
        company_id = get_current_company_id()

        # Validate project exists and belongs to company
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            return {
                "message": "Invalid project_id format",
                "errors": {"validation": "Invalid request"},
            }, 400

        project = Project.query.filter_by(
            id=project_uuid, company_id=company_id
        ).first()
        if not project:
            return {
                "message": PROJECT_NOT_FOUND_MSG,
            }, 404

        # Validate request body
        if not request.is_json:
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data_raw = request.get_json()

        if not isinstance(json_data_raw, dict):
            return {
                "message": INVALID_JSON_BODY_MSG,
            }, 400

        json_data = cast("dict[str, Any]", json_data_raw)

        # Validate sync schema
        try:
            validated_data_raw = self.sync_schema.load(json_data)
            validated_data = cast("dict[str, Any]", validated_data_raw)
        except ValidationError as err:
            return {
                "message": VALIDATION_FAILED_MSG,
                "errors": err.messages,
            }, 422

        tasks_data = validated_data["tasks"]
        updated_count = 0
        not_found_count = 0
        milestone_recalculated_count = 0
        updated_tasks = []
        not_found_uids = []

        # Process each task
        for task_data in tasks_data:
            ms_project_uid = task_data["ms_project_uid"]

            # Find existing task by ms_project_uid
            existing_task = Task.query.filter_by(
                project_id=project_uuid, ms_project_uid=ms_project_uid
            ).first()

            if existing_task:
                # Update existing task (only planning fields)
                if "name" in task_data and task_data["name"] != existing_task.name:
                    existing_task.name = task_data["name"]

                if "planned_start_date" in task_data:
                    new_start = _normalize_datetime(task_data["planned_start_date"])
                    if new_start != existing_task.planned_start_date:
                        existing_task.planned_start_date = new_start

                if "planned_finish_date" in task_data:
                    new_finish = _normalize_datetime(task_data["planned_finish_date"])
                    if new_finish != existing_task.planned_finish_date:
                        existing_task.planned_finish_date = new_finish

                # Update predecessors if provided
                if "predecessors" in task_data:
                    # Remove and recreate predecessors
                    TaskPredecessor.query.filter_by(
                        successor_id=existing_task.id
                    ).delete()

                    for pred in task_data["predecessors"]:
                        # Resolve predecessor by MS Project UID
                        # Support both current and legacy field names
                        pred_uid = pred.get("predecessor_task_uid") or pred.get(
                            "predecessor_ms_project_uid"
                        )
                        if pred_uid is None:
                            continue  # Skip invalid predecessor

                        pred_task = Task.query.filter_by(
                            project_id=project_uuid, ms_project_uid=pred_uid
                        ).first()

                        if pred_task:
                            predecessor_rel = TaskPredecessor()
                            predecessor_rel.successor_id = existing_task.id
                            predecessor_rel.predecessor_id = pred_task.id
                            predecessor_rel.type = pred.get("type", "FS")
                            predecessor_rel.lag_minutes = pred.get("lag", 0)
                            db.session.add(predecessor_rel)

                updated_count += 1
                updated_tasks.append(existing_task)

            else:
                # Task not found - track it
                not_found_count += 1
                not_found_uids.append(ms_project_uid)

        # Commit all changes
        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            return {
                "message": "Database integrity error",
                "errors": {
                    "database": str(e.orig) if hasattr(e, "orig") else str(e),
                },
            }, 409

        # Prepare response matching OpenAPI spec
        response_data = {
            "data": {
                "updated_count": updated_count,
                "not_found_count": not_found_count,
                "milestone_recalculated_count": milestone_recalculated_count,
                "updated_tasks": [
                    self.task_schema.dump(task) for task in updated_tasks
                ],
                "not_found_uids": not_found_uids,
                "not_found_guids": [],  # Not used in current implementation
                # TODO: Implement milestone recalculation
                "recalculated_milestones": [],
            },
            "message": (
                f"{updated_count} tasks updated, {not_found_count} not found, "
                f"{milestone_recalculated_count} milestones recalculated"
            ),
        }

        return response_data, 200
