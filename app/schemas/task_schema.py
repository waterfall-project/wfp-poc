# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Task resource.

Provides schemas for validation, serialization, and deserialization
of task data according to OpenAPI specification.
"""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from marshmallow import Schema, fields, post_dump, pre_load, validates_schema
from marshmallow.exceptions import ValidationError
from marshmallow.validate import Length, OneOf, Range
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.task import Task


class DateOrDateTimeField(fields.Field):
    """Custom field that accepts both date and datetime but stores/returns dates.

    This field handles the mismatch between the OpenAPI spec (format: date-time)
    and the database model (Date columns). It accepts ISO datetime strings from
    API requests and converts them to date objects for storage.
    """

    def _serialize(
        self, value: Any, attr: str | None, obj: Any, **kwargs
    ) -> str | None:
        """Serialize date to ISO format string (YYYY-MM-DD).

        Args:
            value: Date or datetime object.
            attr: Attribute name.
            obj: Parent object.
            **kwargs: Additional marshmallow context arguments.

        Returns:
            ISO format date string or None.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _deserialize(
        self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs
    ) -> date | None:
        """Deserialize ISO date or datetime string to date object.

        Args:
            value: Input string.
            attr: Attribute name.
            data: Parent data dict.
            **kwargs: Additional marshmallow context arguments.

        Returns:
            Date object or None.

        Raises:
            ValidationError: If value is not a valid date/datetime string.
        """
        if value is None:
            return None

        if isinstance(value, date):
            return value

        if not isinstance(value, str):
            raise ValidationError("Not a valid date/datetime string.")

        # Try parsing as datetime first (supports both date and datetime formats)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.date()
        except ValueError:
            # Try parsing as date only
            try:
                return date.fromisoformat(value)
            except ValueError:
                raise ValidationError("Not a valid ISO 8601 date/datetime string.")


class PredecessorSchema(Schema):
    """Schema for task predecessor relationship.

    Represents a predecessor link with relationship type and lag time.
    """

    predecessor_task_id = fields.UUID(required=True)
    type = fields.String(
        required=True,
        validate=OneOf(["FS", "SS", "FF", "SF"]),
        metadata={
            "description": "Relationship type: FS (Finish-to-Start), SS (Start-to-Start), "
            "FF (Finish-to-Finish), SF (Start-to-Finish)"
        },
    )
    lag = fields.Integer(
        load_default=0,
        metadata={"description": "Lag time in minutes (positive=delay, negative=lead)"},
    )


class TaskSchema(SQLAlchemyAutoSchema):
    """Complete Task schema for serialization.

    Read-only schema that includes all fields from the Task model.
    Used for API responses (GET endpoints).
    """

    class Meta:
        """Marshmallow configuration."""

        model = Task
        load_instance = True
        include_fk = True
        include_relationships = False
        exclude = ("wbs_code",)  # Use 'wbs' field instead

    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)
    parent_id = fields.UUID(allow_none=True)

    ms_project_guid = fields.String(allow_none=True, validate=Length(max=50))
    ms_project_uid: fields.Field = fields.Field(allow_none=True)  # Can be int or string
    ms_project_id = fields.Integer(allow_none=True)

    name = fields.String(required=True, validate=Length(min=1, max=255))
    wbs = fields.String(
        allow_none=True, validate=Length(max=50), attribute="wbs_code", data_key="wbs"
    )
    outline_number = fields.String(allow_none=True, validate=Length(max=50))
    outline_level = fields.Integer(allow_none=True, validate=Range(min=0))

    start = DateOrDateTimeField(
        required=True, data_key="start", attribute="planned_start_date"
    )
    planned_start_date = DateOrDateTimeField(
        allow_none=True, dump_only=True, metadata={"deprecated": True}
    )

    finish = DateOrDateTimeField(
        required=True, data_key="finish", attribute="planned_finish_date"
    )
    planned_finish_date = DateOrDateTimeField(
        allow_none=True, dump_only=True, metadata={"deprecated": True}
    )

    duration = fields.String(allow_none=True)
    work = fields.String(allow_none=True)
    cost = fields.Decimal(allow_none=True, as_string=True, places=2)
    fixed_cost = fields.Decimal(load_default=0, as_string=True, places=2)

    is_milestone = fields.Boolean(load_default=False)
    is_summary = fields.Boolean(load_default=False)
    is_deliverable = fields.Boolean(load_default=False)
    is_critical = fields.Boolean(load_default=False)

    status = fields.String(
        load_default="not_started",
        validate=OneOf(["not_started", "in_progress", "completed", "cancelled"]),
    )

    percent_complete = fields.Integer(load_default=0, validate=Range(min=0, max=100))
    percent_work_complete = fields.Integer(
        load_default=0, validate=Range(min=0, max=100)
    )

    early_start = DateOrDateTimeField(allow_none=True, dump_only=True)
    early_finish = DateOrDateTimeField(allow_none=True, dump_only=True)
    late_start = DateOrDateTimeField(allow_none=True, dump_only=True)
    late_finish = DateOrDateTimeField(allow_none=True, dump_only=True)
    total_slack = fields.Integer(load_default=0, dump_only=True)
    free_slack = fields.Integer(load_default=0, dump_only=True)

    manual_scheduling = fields.Boolean(load_default=False)

    actual_start = DateOrDateTimeField(allow_none=True)
    actual_finish = DateOrDateTimeField(allow_none=True)
    actual_cost = fields.Decimal(load_default=0, as_string=True, places=2)
    actual_work = fields.String(allow_none=True)

    remaining_cost = fields.Decimal(allow_none=True, as_string=True, places=2)
    remaining_work = fields.String(allow_none=True)

    predecessors = fields.List(fields.Nested(PredecessorSchema), load_default=list)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_dump
    def add_deprecated_aliases(self, data: dict, **kwargs: Any) -> dict:
        """Add deprecated field aliases for backward compatibility.

        Args:
            data: Serialized task data.
            **kwargs: Additional marshmallow context arguments.

        Returns:
            Data with deprecated aliases added.
        """
        if "start" in data:
            data["planned_start_date"] = data["start"]
        if "finish" in data:
            data["planned_finish_date"] = data["finish"]
        return data


class TaskCreateSchema(Schema):
    """Schema for creating a new task.

    Validates input for POST /v0/projects/{project_id}/tasks.
    """

    parent_id = fields.UUID(allow_none=True)
    ms_project_uid: fields.Field = fields.Field(allow_none=True)
    ms_project_id = fields.Integer(allow_none=True)
    ms_project_guid = fields.String(allow_none=True, validate=Length(max=50))

    name = fields.String(required=True, validate=Length(min=1, max=255))
    wbs = fields.String(allow_none=True, validate=Length(max=50))
    outline_number = fields.String(allow_none=True, validate=Length(max=50))
    outline_level = fields.Integer(allow_none=True, validate=Range(min=0))

    start = DateOrDateTimeField(required=True)
    planned_start_date = DateOrDateTimeField(
        allow_none=True, metadata={"deprecated": True}
    )
    finish = DateOrDateTimeField(required=True)
    planned_finish_date = DateOrDateTimeField(
        allow_none=True, metadata={"deprecated": True}
    )

    duration = fields.String(allow_none=True)
    work = fields.String(allow_none=True)
    cost = fields.Decimal(
        allow_none=True, as_string=True, places=2, validate=Range(min=0)
    )
    fixed_cost = fields.Decimal(load_default=0, as_string=True, places=2)

    is_milestone = fields.Boolean(load_default=False)
    is_summary = fields.Boolean(load_default=False)
    is_deliverable = fields.Boolean(load_default=False)

    status = fields.String(
        load_default="not_started",
        validate=OneOf(["not_started", "in_progress", "completed", "cancelled"]),
    )

    percent_complete = fields.Integer(load_default=0, validate=Range(min=0, max=100))
    manual_scheduling = fields.Boolean(load_default=False)

    predecessors = fields.List(fields.Nested(PredecessorSchema), load_default=list)

    @pre_load
    def handle_deprecated_aliases(self, data: dict, **kwargs: Any) -> dict:
        """Handle deprecated field aliases.

        Maps planned_start_date -> start and planned_finish_date -> finish if present.

        Args:
            data: Input data.
            **kwargs: Additional marshmallow context arguments.

        Returns:
            Data with aliases resolved.
        """
        if "planned_start_date" in data and "start" not in data:
            data["start"] = data["planned_start_date"]
        if "planned_finish_date" in data and "finish" not in data:
            data["finish"] = data["planned_finish_date"]
        return data

    @validates_schema
    def validate_dates(self, data: dict, **kwargs: Any) -> None:
        """Validate that finish date is after start date.

        Args:
            data: Validated data.
            **kwargs: Additional marshmallow context arguments.

        Raises:
            ValidationError: If finish is before start.
        """
        start = data.get("start")
        finish = data.get("finish")
        if start and finish and finish < start:
            raise ValidationError("Finish date must be after or equal to start date")


class TaskUpdateSchema(Schema):
    """Schema for updating a task (partial update).

    Validates input for PATCH /v0/projects/{project_id}/tasks/{id}.
    """

    name = fields.String(allow_none=True, validate=Length(min=1, max=255))
    ms_project_uid: fields.Field = fields.Field(allow_none=True)

    start = DateOrDateTimeField(allow_none=True)
    planned_start_date = DateOrDateTimeField(
        allow_none=True, metadata={"deprecated": True}
    )
    finish = DateOrDateTimeField(allow_none=True)
    planned_finish_date = DateOrDateTimeField(
        allow_none=True, metadata={"deprecated": True}
    )

    status = fields.String(
        allow_none=True,
        validate=OneOf(["not_started", "in_progress", "completed", "cancelled"]),
    )

    percent_complete = fields.Integer(allow_none=True, validate=Range(min=0, max=100))

    actual_start = DateOrDateTimeField(allow_none=True)
    actual_finish = DateOrDateTimeField(allow_none=True)
    remaining_cost = fields.Decimal(allow_none=True, as_string=True, places=2)

    predecessors = fields.List(fields.Nested(PredecessorSchema), allow_none=True)

    @pre_load
    def handle_deprecated_aliases(self, data: dict, **kwargs: Any) -> dict:
        """Handle deprecated field aliases.

        Args:
            data: Input data.
            **kwargs: Additional marshmallow context arguments.

        Returns:
            Data with aliases resolved.
        """
        if "planned_start_date" in data and "start" not in data:
            data["start"] = data["planned_start_date"]
        if "planned_finish_date" in data and "finish" not in data:
            data["finish"] = data["planned_finish_date"]
        return data

    @validates_schema
    def validate_at_least_one_field(self, data: dict, **kwargs: Any) -> None:
        """Validate that at least one field is provided for update.

        Args:
            data: Validated data.
            **kwargs: Additional marshmallow context arguments.

        Raises:
            ValidationError: If no fields are provided.
        """
        if not data:
            raise ValidationError("At least one field must be provided for update")

    @validates_schema
    def validate_dates(self, data: dict, **kwargs: Any) -> None:
        """Validate date consistency.

        Args:
            data: Validated data.
            **kwargs: Additional marshmallow context arguments.

        Raises:
            ValidationError: If dates are inconsistent.
        """
        start = data.get("start")
        finish = data.get("finish")
        if start and finish and finish < start:
            raise ValidationError("Finish date must be after or equal to start date")


class TaskResponseSchema(Schema):
    """Schema for single task response.

    Wraps task data in standard response format.
    """

    data = fields.Nested(TaskSchema, required=True)
    message = fields.String(allow_none=True)


class TaskListSchema(Schema):
    """Schema for paginated task list response.

    Provides pagination metadata with task array.
    """

    data = fields.List(fields.Nested(TaskSchema), required=True)
    page = fields.Integer(required=True, validate=Range(min=1))
    per_page = fields.Integer(required=True, validate=Range(min=1, max=100))
    total = fields.Integer(required=True, validate=Range(min=0))
    total_pages = fields.Integer(required=True, validate=Range(min=0))


class TaskBulkCreateSchema(Schema):
    """Schema for bulk task creation.

    Validates input for POST /v0/projects/{project_id}/tasks/bulk.
    """

    tasks = fields.List(
        fields.Nested(TaskCreateSchema),
        required=True,
        validate=Length(min=1, max=500),
    )


class TaskBulkItemResultSchema(Schema):
    """Schema for individual task result in bulk operation."""

    index = fields.Integer(required=True)
    task_name = fields.String(allow_none=True)
    errors = fields.Dict(allow_none=True)


class TaskBulkResponseSchema(Schema):
    """Schema for bulk task creation response."""

    data = fields.Dict(
        required=True,
        keys=fields.String(),
        values=fields.Field(),
        metadata={
            "properties": {
                "created_count": "integer",
                "failed_count": "integer",
                "tasks": "array",
                "errors": "array",
            }
        },
    )
    message = fields.String(required=True)


class TaskSyncItemSchema(Schema):
    """Schema for a single task in sync operation.

    Uses ms_project_uid as reconciliation key.
    """

    ms_project_uid: fields.Field = fields.Field(
        required=True, metadata={"description": "Reconciliation key"}
    )
    name = fields.String(allow_none=True, validate=Length(min=1, max=255))
    planned_start_date = DateOrDateTimeField(allow_none=True)
    planned_finish_date = DateOrDateTimeField(allow_none=True)
    duration = fields.String(allow_none=True)
    predecessors = fields.List(fields.Nested(PredecessorSchema), allow_none=True)


class TaskSyncSchema(Schema):
    """Schema for task sync (upsert) operation.

    Validates input for PUT /v0/projects/{project_id}/tasks/sync.
    """

    tasks = fields.List(
        fields.Nested(TaskSyncItemSchema),
        required=True,
        validate=Length(min=1, max=500),
    )


class TaskSyncResponseSchema(Schema):
    """Schema for task sync response.

    Conforms to OpenAPI specification with updated_count, not_found_count,
    and milestone_recalculated_count.
    """

    data = fields.Dict(
        required=True,
        metadata={
            "properties": {
                "updated_count": "integer",
                "not_found_count": "integer",
                "milestone_recalculated_count": "integer",
                "updated_tasks": "array",
                "not_found_guids": "array",
                "not_found_uids": "array",
                "recalculated_milestones": "array",
            }
        },
    )
    message = fields.String(required=True)
