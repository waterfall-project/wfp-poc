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

from marshmallow import Schema, ValidationError, fields, post_dump, validates_schema
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
        exclude = ("ms_project_uid", "current_rae", "current_rae_date")

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
        places=4,
        validate=Range(min=0, max=1),
    )

    is_achieved = fields.Boolean(required=True, dump_default=False)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_dump
    def convert_decimal_fields(
        self, data: dict[str, object], **kwargs: object
    ) -> dict[str, object]:
        """Convert Decimal fields to float for JSON responses.

        Args:
            data: Serialized milestone data.
            **kwargs: Additional keyword arguments.

        Returns:
            Serialized data with Decimal fields converted to float.
        """
        budget_weight = data.get("budget_weight")
        if isinstance(budget_weight, Decimal):
            data["budget_weight"] = float(budget_weight)
        return data


class MilestoneCreateSchema(Schema):
    """Schema for creating a milestone.

    Validates POST /v0/projects/{project_id}/milestones request body.
    """

    name = fields.String(required=True, validate=Length(min=1, max=255))
    description = fields.String(validate=Length(max=1000))

    target_date = fields.DateTime(required=True)

    budget_weight = fields.Decimal(
        required=True,
        as_string=True,
        places=4,
        validate=Range(min=0, max=1),
    )


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
        as_string=True,
        places=4,
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
