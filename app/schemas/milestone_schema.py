# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Milestone resource.

Provides schemas for validation, serialization, and deserialization
of milestone data according to OpenAPI specification.
"""

from decimal import Decimal

from marshmallow import Schema, ValidationError, fields, validates, validates_schema
from marshmallow.validate import Length, OneOf, Range
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.milestone import Milestone


class MilestoneSchema(SQLAlchemyAutoSchema):
    """Complete Milestone schema for serialization.

    Read-only schema that includes all fields from the Milestone model.
    Used for API responses (GET endpoints).
    """

    class Meta:
        """Marshmallow configuration."""

        model = Milestone
        load_instance = True
        include_fk = True
        include_relationships = False

    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(required=True)

    name = fields.String(required=True, validate=Length(min=1, max=255))
    description = fields.String(allow_none=True, validate=Length(max=1000))

    target_date = fields.DateTime(required=True)
    actual_date = fields.DateTime(allow_none=True)
    achieved_date = fields.DateTime(allow_none=True)

    status = fields.String(
        required=True,
        validate=OneOf(["upcoming", "achieved", "missed"]),
        dump_default="upcoming",
    )

    budget_weight = fields.Decimal(
        required=True,
        as_string=False,
        places=6,
        validate=Range(min=0, max=1),
    )

    is_achieved = fields.Boolean(required=True, dump_default=False)

    ms_project_uid = fields.Integer(allow_none=True)
    current_rae = fields.Decimal(allow_none=True, as_string=False, places=2)
    current_rae_date = fields.DateTime(allow_none=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class MilestoneCreateSchema(Schema):
    """Schema for creating a milestone.

    Validates POST /v0/projects/{project_id}/milestones request body.
    """

    name = fields.String(required=True, validate=Length(min=1, max=255))
    description = fields.String(allow_none=True, validate=Length(max=1000))

    target_date = fields.DateTime(required=True)

    budget_weight = fields.Decimal(
        required=True,
        as_string=False,
        places=6,
        validate=Range(min=0, max=1),
    )

    @validates("budget_weight")
    def validate_budget_weight(self, value: Decimal) -> None:
        """Validate budget_weight is between 0 and 1.

        Args:
            value: The budget_weight value to validate.

        Raises:
            ValidationError: If value is not in valid range.
        """
        if value < 0 or value > 1:
            raise ValidationError("budget_weight must be between 0.0 and 1.0")


class MilestoneUpdateSchema(Schema):
    """Schema for updating a milestone (partial update).

    Validates PATCH /v0/projects/{project_id}/milestones/{id} request body.
    All fields are optional (partial update).
    """

    name = fields.String(validate=Length(min=1, max=255))
    description = fields.String(allow_none=True, validate=Length(max=1000))

    target_date = fields.DateTime()
    actual_date = fields.DateTime(allow_none=True)
    achieved_date = fields.DateTime(allow_none=True)

    budget_weight = fields.Decimal(
        as_string=False,
        places=6,
        validate=Range(min=0, max=1),
    )

    is_achieved = fields.Boolean()

    @validates_schema
    def validate_at_least_one_field(self, data, **kwargs) -> None:
        """Ensure at least one field is provided for update.

        Args:
            data: The input data dictionary.
            **kwargs: Additional keyword arguments.

        Raises:
            ValidationError: If no fields are provided.
        """
        if not data:
            raise ValidationError("At least one field must be provided for update")


class MilestoneListResponseSchema(Schema):
    """Schema for milestone list response.

    Validates GET /v0/projects/{project_id}/milestones response.
    """

    data = fields.List(fields.Nested(MilestoneSchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)


class MilestoneResponseSchema(Schema):
    """Schema for single milestone response.

    Validates POST/GET/PATCH milestone responses.
    """

    data = fields.Nested(MilestoneSchema, required=True)
    message = fields.String(allow_none=True)


class MilestoneTaskLinkSchema(Schema):
    """Schema for linking tasks to a milestone.

    Validates POST /v0/milestones/{milestone_id}/tasks request body.
    """

    task_ids = fields.List(
        fields.UUID(),
        required=True,
        validate=Length(min=1),
    )

    relationship_type = fields.String(
        validate=OneOf(["predecessor", "contributor"]),
        dump_default="predecessor",
        load_default="predecessor",
    )


class MilestoneTaskInfoSchema(Schema):
    """Schema for task information in milestone-task responses."""

    id = fields.UUID(required=True)
    name = fields.String(required=True)
    wbs = fields.String(allow_none=True)
    planned_finish_date = fields.DateTime(required=True)
    planned_finish = fields.DateTime(
        dump_only=True,
        attribute="planned_finish_date",
    )  # Alias for backwards compatibility
    is_critical = fields.Boolean(required=True)
    ms_project_uid = fields.Integer(allow_none=True)


class MilestoneTaskLinkResponseSchema(Schema):
    """Schema for milestone-task link operation response.

    Validates POST/PUT milestone-task link responses.
    """

    data = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=True,
    )
    message = fields.String(allow_none=True)


class MilestonePredecessorTasksResponseSchema(Schema):
    """Schema for GET /v0/milestones/{milestone_id}/tasks response."""

    data = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=True,
    )
