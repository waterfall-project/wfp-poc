# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Project resource.

Provides schemas for validation, serialization, and deserialization
of project data according to OpenAPI specification.
"""

from datetime import time
from decimal import Decimal

from marshmallow import Schema, fields, post_dump
from marshmallow.validate import Length, Range
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.project import Project


class ProjectSchema(SQLAlchemyAutoSchema):
    """Complete Project schema for serialization.

    Read-only schema that includes all fields from the Project model.
    Used for API responses (GET endpoints).
    """

    class Meta:
        """Marshmallow configuration."""

        model = Project
        load_instance = True
        include_fk = True
        include_relationships = False

    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(dump_only=True)

    name = fields.String(required=True, validate=Length(min=1, max=255))
    code = fields.String(allow_none=True, validate=Length(max=50))
    title = fields.String(allow_none=True, validate=Length(max=255))
    description = fields.String(allow_none=True, validate=Length(max=2000))

    start_date = fields.DateTime(required=True)
    planned_start_date = fields.DateTime(allow_none=True)
    finish_date = fields.DateTime(required=True)
    planned_finish_date = fields.DateTime(allow_none=True)

    budget = fields.Decimal(allow_none=True, places=2, validate=Range(min=0))
    currency_code = fields.String(validate=Length(equal=3), load_default="EUR")

    status = fields.String(
        validate=lambda x: x
        in ["initialized", "active", "completed", "cancelled", "on_hold"],
        load_default="initialized",
    )

    ms_project_uid = fields.String(allow_none=True)
    ms_project_guid = fields.String(allow_none=True, validate=Length(max=50))
    ms_project_save_version = fields.Integer(allow_none=True)

    creation_date = fields.DateTime(allow_none=True)
    last_saved_date = fields.DateTime(allow_none=True)
    calendar_uid = fields.Integer(allow_none=True)

    minutes_per_day = fields.Integer(load_default=420, validate=Range(min=0))
    minutes_per_week = fields.Integer(load_default=2100, validate=Range(min=0))
    days_per_month = fields.Integer(load_default=20, validate=Range(min=0))
    week_start_day = fields.Integer(load_default=1, validate=Range(min=0, max=6))

    default_start_time = fields.Time(load_default=time(9, 0, 0))
    default_finish_time = fields.Time(load_default=time(18, 0, 0))

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_dump
    def convert_decimals(self, data: dict, **kwargs) -> dict:
        """Convert Decimal fields to float for JSON serialization.

        Args:
            data: Serialized data dictionary.
            **kwargs: Additional keyword arguments from Marshmallow.

        Returns:
            Modified data with Decimal values converted to float.
        """
        if data.get("budget") is not None and isinstance(data["budget"], Decimal):
            data["budget"] = float(data["budget"])
        return data


class ProjectCreateSchema(Schema):
    """Schema for creating a new project.

    Validates required fields and business rules for project creation.
    """

    name = fields.String(required=True, validate=Length(min=1, max=255))
    code = fields.String(required=True, validate=Length(min=1, max=50))
    title = fields.String(allow_none=True, validate=Length(max=255))
    description = fields.String(allow_none=True, validate=Length(max=2000))

    start_date = fields.DateTime(required=True)
    planned_start_date = fields.DateTime(allow_none=True)
    finish_date = fields.DateTime(required=True)
    planned_finish_date = fields.DateTime(allow_none=True)

    budget = fields.Decimal(allow_none=True, places=2, validate=Range(min=0))
    currency_code = fields.String(validate=Length(equal=3), load_default="EUR")

    status = fields.String(
        allow_none=True,
        validate=lambda x: x
        in ["initialized", "active", "completed", "cancelled", "on_hold"]
        if x
        else True,
        load_default="initialized",
    )

    ms_project_uid = fields.String(allow_none=True)
    ms_project_guid = fields.String(allow_none=True, validate=Length(max=50))
    ms_project_save_version = fields.Integer(allow_none=True)
    creation_date = fields.DateTime(allow_none=True)
    last_saved_date = fields.DateTime(allow_none=True)
    calendar_uid = fields.Integer(allow_none=True)

    minutes_per_day = fields.Integer(load_default=420, validate=Range(min=0))
    minutes_per_week = fields.Integer(load_default=2100, validate=Range(min=0))
    days_per_month = fields.Integer(load_default=20, validate=Range(min=0))
    week_start_day = fields.Integer(load_default=1, validate=Range(min=0, max=6))
    default_start_time = fields.Time(load_default=time(9, 0, 0))
    default_finish_time = fields.Time(load_default=time(18, 0, 0))


class ProjectUpdateSchema(Schema):
    """Schema for updating an existing project.

    All fields are optional (partial update with PATCH).
    """

    name = fields.String(validate=Length(min=1, max=255))
    code = fields.String(allow_none=True, validate=Length(min=1, max=50))
    title = fields.String(allow_none=True, validate=Length(max=255))
    description = fields.String(allow_none=True, validate=Length(max=2000))

    start_date = fields.DateTime()
    planned_start_date = fields.DateTime(allow_none=True)
    finish_date = fields.DateTime()
    planned_finish_date = fields.DateTime(allow_none=True)

    budget = fields.Decimal(allow_none=True, places=2, validate=Range(min=0))
    currency_code = fields.String(validate=Length(equal=3))

    status = fields.String(
        allow_none=True,
        validate=lambda x: x
        in ["initialized", "active", "completed", "cancelled", "on_hold"]
        if x
        else True,
    )
    ms_project_uid = fields.String(allow_none=True)
    ms_project_guid = fields.String(allow_none=True, validate=Length(max=50))
    ms_project_save_version = fields.Integer(allow_none=True)
    creation_date = fields.DateTime(allow_none=True)
    last_saved_date = fields.DateTime(allow_none=True)
    calendar_uid = fields.Integer(allow_none=True)

    minutes_per_day = fields.Integer(validate=Range(min=0))
    minutes_per_week = fields.Integer(validate=Range(min=0))
    days_per_month = fields.Integer(validate=Range(min=0))
    week_start_day = fields.Integer(validate=Range(min=0, max=6))
    default_start_time = fields.Time()
    default_finish_time = fields.Time()


class ProjectListResponseSchema(Schema):
    """Schema for paginated project list response.

    Returns projects with pagination metadata.
    """

    data = fields.List(fields.Nested(ProjectSchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)


class ProjectResponseSchema(Schema):
    """Schema for single project response.

    Wraps project data with optional message.
    """

    data = fields.Nested(ProjectSchema, required=True)
    message = fields.String()
