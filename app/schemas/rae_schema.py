# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for RAE endpoints.

Defines validation and serialization schemas for milestone RAE updates,
history retrieval, and project-wide RAE summary responses.
"""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validates_schema
from marshmallow.validate import Length, OneOf, Range

SORT_ORDER_VALUES = ["asc", "desc"]


class RAECreateTaskEstimateSchema(Schema):
    """Schema for task-level RAE estimate items."""

    task_id = fields.UUID(required=True)
    task_name = fields.String(required=True, validate=Length(min=1, max=255))
    remaining_cost = fields.Float(required=True, validate=Range(min=0))
    comment = fields.String(allow_none=True, validate=Length(max=500))


class RAECreateDetailsSchema(Schema):
    """Schema for optional RAE details payload."""

    task_estimates = fields.List(fields.Nested(RAECreateTaskEstimateSchema))


class RAECreateSchema(Schema):
    """Schema for creating a milestone RAE entry."""

    date = fields.DateTime(required=True)
    amount = fields.Float(required=True, validate=Range(min=0))
    comment = fields.String(allow_none=True, validate=Length(max=500))
    details = fields.Nested(RAECreateDetailsSchema, allow_none=True)


class RAESchema(Schema):
    """Schema for RAE response items."""

    id = fields.UUID(required=True)
    milestone_id = fields.UUID(required=True)
    date = fields.DateTime(required=True)
    amount = fields.Float(required=True)
    comment = fields.String(allow_none=True, validate=Length(max=500))
    details = fields.Dict(allow_none=True)
    updated_by = fields.UUID(required=True)
    created_at = fields.DateTime(required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class RAEResponseSchema(Schema):
    """Schema for RAE create response."""

    data = fields.Nested(RAESchema, required=True)
    message = fields.String(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class RAEHistoryQuerySchema(Schema):
    """Schema for RAE history query parameters."""

    page = fields.Integer(load_default=1, validate=Range(min=1))
    per_page = fields.Integer(load_default=20, validate=Range(min=1, max=100))
    date_from = fields.DateTime(load_default=None)
    date_to = fields.DateTime(load_default=None)
    sort_order = fields.String(load_default="asc", validate=OneOf(SORT_ORDER_VALUES))

    @validates_schema
    def validate_date_range(self, data: dict, **kwargs: object) -> None:
        """Validate date_from <= date_to when both provided."""
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                "date_from must be before or equal to date_to",
                field_name="date_from",
            )


class RAEHistoryResponseSchema(Schema):
    """Schema for paginated RAE history responses."""

    data = fields.List(fields.Nested(RAESchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class RAESummaryMilestoneSchema(Schema):
    """Schema for milestone summary entries in RAE summary."""

    milestone_id = fields.UUID(required=True)
    name = fields.String(required=True)
    budget_weight = fields.Float(required=True)
    rae = fields.Float(required=True)
    rae_date = fields.DateTime(allow_none=True)
    achieved = fields.Boolean(required=True)
    comment = fields.String(allow_none=True, validate=Length(max=500))

    class Meta:
        """Schema configuration."""

        ordered = True


class RAESummaryDataSchema(Schema):
    """Schema for project RAE summary data."""

    project_id = fields.UUID(required=True)
    as_of_date = fields.DateTime(required=True)
    total_rae = fields.Float(required=True)
    milestones = fields.List(fields.Nested(RAESummaryMilestoneSchema), required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class RAESummaryResponseSchema(Schema):
    """Schema for RAE summary responses."""

    data = fields.Nested(RAESummaryDataSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class RAESummaryQuerySchema(Schema):
    """Schema for project RAE summary query parameters."""

    as_of_date = fields.DateTime(load_default=None)
