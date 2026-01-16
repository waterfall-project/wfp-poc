# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Assignment entity.

Provides validation and serialization for assignment endpoints, including
conversion between ISO 8601 duration strings and the internal minute-based
storage used by the Assignment model.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from marshmallow import Schema, ValidationError, fields, post_dump, validates_schema
from marshmallow.validate import Range

if TYPE_CHECKING:
    from app.models.assignment import Assignment

_DURATION_PATTERN = re.compile(r"^PT(\d+)H(\d+)M(\d+)S$")


def _validate_ms_project_uid(value: Any) -> None:
    """Validate MS Project UID accepts integer or numeric string.

    Args:
        value: Value to validate (int, str, or None).

    Raises:
        ValidationError: If value is not a non-negative integer or numeric string.
    """
    if value is None:
        return

    if isinstance(value, int):
        if value < 0:
            raise ValidationError("ms_project_uid must be non-negative")
        return

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            raise ValidationError("ms_project_uid cannot be empty")
        if trimmed.isdigit():
            return
        if trimmed.startswith("-") and trimmed[1:].isdigit():
            raise ValidationError("ms_project_uid must be non-negative")

    raise ValidationError(
        "ms_project_uid must be a non-negative integer or numeric string"
    )


def _duration_to_minutes(value: str | None) -> int | None:
    """Convert ISO 8601 duration string (PT#H#M#S) to total minutes.

    Args:
        value: Duration string.

    Returns:
        Total minutes as integer or None.

    Raises:
        ValidationError: If the string does not match the expected pattern.
    """
    if value is None:
        return None

    match = _DURATION_PATTERN.fullmatch(value)
    if not match:
        raise ValidationError("Duration must match pattern PT#H#M#S")

    hours, minutes, seconds = (int(part) for part in match.groups())
    total_minutes = (hours * 60) + minutes + (seconds // 60)
    return total_minutes


def _minutes_to_duration(minutes: int | None) -> str | None:
    """Convert minutes to ISO 8601 duration string (PT#H#M0S)."""
    if minutes is None:
        return None

    hours, remaining_minutes = divmod(minutes, 60)
    return f"PT{hours}H{remaining_minutes}M0S"


class AssignmentSchema(Schema):
    """Base schema for assignment serialization."""

    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    task_id = fields.UUID(required=True)
    resource_id = fields.UUID(required=True)
    ms_project_uid = fields.Integer(allow_none=True)

    work_hours = fields.Method(
        serialize="_get_work_hours", deserialize="_load_work_hours", allow_none=True
    )
    percent_allocation = fields.Integer(required=True, validate=Range(min=0, max=100))
    cost = fields.Method(
        serialize="_get_planned_cost", deserialize="_load_planned_cost", allow_none=True
    )
    actual_work = fields.Method(
        serialize="_get_actual_work", deserialize="_load_actual_work", allow_none=True
    )
    actual_cost = fields.Method(
        serialize="_get_actual_cost", deserialize="_load_actual_cost", allow_none=True
    )

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    def _get_work_hours(self, obj: Assignment) -> str | None:  # noqa: D401
        return _minutes_to_duration(getattr(obj, "planned_work_minutes", None))

    def _load_work_hours(self, value: str | None) -> int | None:  # noqa: D401
        return _duration_to_minutes(value)

    def _get_actual_work(self, obj: Assignment) -> str | None:  # noqa: D401
        return _minutes_to_duration(getattr(obj, "actual_work_minutes", None))

    def _load_actual_work(self, value: str | None) -> int | None:  # noqa: D401
        return _duration_to_minutes(value)

    def _get_planned_cost(self, obj: Assignment) -> float | None:  # noqa: D401
        cost = getattr(obj, "planned_cost", None)
        return float(cost) if isinstance(cost, Decimal) else cost

    def _load_planned_cost(self, value: float | int | None) -> float | None:  # noqa: D401
        if value is None:
            return None
        if value < 0:
            raise ValidationError("cost must be greater than or equal to 0")
        return float(value)

    def _get_actual_cost(self, obj: Assignment) -> float | None:  # noqa: D401
        cost = getattr(obj, "actual_cost", None)
        return float(cost) if isinstance(cost, Decimal) else cost

    def _load_actual_cost(self, value: float | int | None) -> float | None:  # noqa: D401
        if value is None:
            return None
        if value < 0:
            raise ValidationError("actual_cost must be greater than or equal to 0")
        return float(value)

    @post_dump
    def remove_internal_fields(
        self, data: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Remove internal minute-based fields if present after serialization."""
        data.pop("planned_work_minutes", None)
        data.pop("actual_work_minutes", None)
        return data

    class Meta:
        """Schema configuration."""

        ordered = True
        load_only = ("planned_work_minutes", "actual_work_minutes", "planned_cost")


class AssignmentCreateSchema(Schema):
    """Schema for creating a new assignment."""

    task_id = fields.UUID(required=True)
    resource_id = fields.UUID(required=True)
    ms_project_uid = fields.Raw(validate=_validate_ms_project_uid, allow_none=True)
    work_hours = fields.String(
        allow_none=True, validate=lambda v: _duration_to_minutes(v)
    )
    percent_allocation = fields.Integer(
        load_default=100, validate=Range(min=0, max=100)
    )
    cost = fields.Decimal(
        allow_none=True, as_string=True, places=2, validate=Range(min=0)
    )

    @post_dump
    def convert_decimals(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Convert Decimal cost to float in responses if needed."""
        if "cost" in data and isinstance(data["cost"], Decimal):
            data["cost"] = float(data["cost"])
        return data


class AssignmentUpdateSchema(Schema):
    """Schema for partially updating an assignment."""

    work_hours = fields.String(
        allow_none=True, validate=lambda v: _duration_to_minutes(v)
    )
    percent_allocation = fields.Integer(validate=Range(min=0, max=100))
    cost = fields.Decimal(
        allow_none=True, as_string=True, places=2, validate=Range(min=0)
    )
    actual_work = fields.String(
        allow_none=True, validate=lambda v: _duration_to_minutes(v)
    )
    actual_cost = fields.Decimal(
        allow_none=True, as_string=True, places=2, validate=Range(min=0)
    )

    @validates_schema
    def validate_non_empty(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Ensure at least one field is provided for update."""
        if not data:
            raise ValidationError(
                "At least one field must be provided for update",
                field_name="_schema",
            )

    @post_dump
    def convert_decimals(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Convert Decimal values to float for JSON responses."""
        for key in ["cost", "actual_cost"]:
            if key in data and isinstance(data[key], Decimal):
                data[key] = float(data[key])
        return data


class AssignmentResponseSchema(Schema):
    """Schema for a single assignment response."""

    data = fields.Nested(AssignmentSchema, required=True)
    message = fields.String()


class AssignmentListResponseSchema(Schema):
    """Schema for paginated assignment list responses."""

    data = fields.List(fields.Nested(AssignmentSchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)
