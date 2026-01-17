# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for progress updates.

Defines request and response schemas for bulk progress updates and
progress history retrieval following the OpenAPI specification.
"""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validates_schema
from marshmallow.validate import Length, OneOf, Range

TASK_STATUS_VALUES = ["not_started", "in_progress", "completed", "cancelled"]


class ProgressUpdateEntrySchema(Schema):
    """Schema for a single task progress update entry."""

    task_id = fields.UUID(required=True)
    percent_complete = fields.Integer(required=True, validate=Range(min=0, max=100))
    comment = fields.String(validate=Length(max=255))


class ProgressUpdateRequestSchema(Schema):
    """Schema for bulk progress update requests."""

    date = fields.DateTime(required=True)
    updates = fields.List(
        fields.Nested(ProgressUpdateEntrySchema),
        required=True,
        validate=Length(min=1),
    )


class ProgressUpdateResultItemSchema(Schema):
    """Schema for a successful progress update item."""

    task_id = fields.UUID(required=True)
    task_name = fields.String(required=True)
    previous_percent_complete = fields.Integer(
        required=True, validate=Range(min=0, max=100)
    )
    new_percent_complete = fields.Integer(required=True, validate=Range(min=0, max=100))
    status_changed = fields.Boolean(required=True)
    new_status = fields.String(validate=OneOf(TASK_STATUS_VALUES))


class ProgressUpdateErrorSchema(Schema):
    """Schema for a failed progress update entry."""

    task_id = fields.UUID(required=True)
    error = fields.String(required=True)


class ProgressUpdateDataSchema(Schema):
    """Schema for progress update response data."""

    project_id = fields.UUID(required=True)
    date = fields.DateTime(required=True)
    updated_count = fields.Integer(required=True)
    failed_count = fields.Integer(required=True)
    updates = fields.List(fields.Nested(ProgressUpdateResultItemSchema), required=True)
    errors = fields.List(fields.Nested(ProgressUpdateErrorSchema), required=True)


class ProgressUpdateResponseSchema(Schema):
    """Schema for bulk progress update responses."""

    data = fields.Nested(ProgressUpdateDataSchema, required=True)
    message = fields.String(allow_none=True)


class ProgressHistoryItemSchema(Schema):
    """Schema for progress history items."""

    id = fields.UUID(required=True)
    project_id = fields.UUID(required=True)
    task_id = fields.UUID(required=True)
    task_name = fields.String(required=True)
    date = fields.DateTime(required=True)
    previous_percent_complete = fields.Integer(
        required=True, validate=Range(min=0, max=100)
    )
    new_percent_complete = fields.Integer(required=True, validate=Range(min=0, max=100))
    delta = fields.Integer(required=True)
    comment = fields.String(allow_none=True, validate=Length(max=255))
    updated_by = fields.UUID(required=True)
    created_at = fields.DateTime(required=True)


class ProgressHistoryResponseSchema(Schema):
    """Schema for paginated progress history responses."""

    data = fields.List(fields.Nested(ProgressHistoryItemSchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)


class ProgressHistoryQuerySchema(Schema):
    """Schema for validating progress history query parameters."""

    task_id = fields.UUID()
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    page = fields.Integer(load_default=1, validate=Range(min=1))
    per_page = fields.Integer(load_default=20, validate=Range(min=1, max=100))
    sort_order = fields.String(load_default="desc", validate=OneOf(["asc", "desc"]))

    @validates_schema
    def validate_date_range(self, data: dict, **kwargs: object) -> None:
        """Validate start_date <= end_date when both provided."""
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise ValidationError(
                "start_date must be before or equal to end_date",
                field_name="start_date",
            )
