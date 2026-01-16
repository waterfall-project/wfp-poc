# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Resource entity.

Provides schemas for validation, serialization, and deserialization of
resource data according to the OpenAPI specification.
"""

from decimal import Decimal
from typing import Any

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_dump,
    post_load,
    validates_schema,
)
from marshmallow.validate import Length, OneOf, Range
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models.resource import Resource


def _validate_ms_project_uid(value: Any) -> None:
    """Validate MS Project UID accepts integer or numeric string.

    This validator is designed to be reusable for both required and optional
    fields. When the value is ``None``, it returns without error and relies
    on the Marshmallow field configuration (``required``/``allow_none``) to
    decide whether ``None`` is acceptable.

    Args:
        value: Value to validate (int, str, or None).

    Raises:
        ValidationError: If value is not a non-negative integer or numeric string.
    """
    # Allow None to pass through so that optional fields using this validator
    # do not fail validation solely due to a null value. Marshmallow will
    # enforce required/allow_none semantics at the field level.
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
        # Only accept non-negative numeric strings for consistency
        if trimmed.isdigit():
            return
        # Check for negative numeric string and reject it
        if trimmed.startswith("-") and trimmed[1:].isdigit():
            raise ValidationError("ms_project_uid must be non-negative")

    raise ValidationError(
        "ms_project_uid must be a non-negative integer or numeric string"
    )


class ResourceSchema(SQLAlchemyAutoSchema):
    """Complete Resource schema for serialization.

    Read-only schema that includes all fields from the Resource model.
    Used for API responses.
    """

    class Meta:
        """Marshmallow configuration."""

        model = Resource
        load_instance = True
        include_fk = True
        include_relationships = False

    id = fields.UUID(dump_only=True)
    company_id = fields.UUID(dump_only=True)

    ms_project_uid = fields.Integer(allow_none=True)
    name = fields.String(required=True, validate=Length(min=1, max=255))
    type = fields.String(
        validate=OneOf(["labor", "material", "cost"]), load_default="labor"
    )
    standard_rate = fields.Decimal(
        allow_none=False, places=2, validate=Range(min=0), load_default=0
    )
    overtime_rate = fields.Decimal(
        allow_none=False, places=2, validate=Range(min=0), load_default=0
    )
    email = fields.Email(allow_none=True, validate=Length(max=255))
    is_active = fields.Boolean(load_default=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_dump
    def convert_decimals(self, data: dict, **kwargs) -> dict:
        """Convert Decimal fields to float for JSON serialization."""
        for field in ["standard_rate", "overtime_rate"]:
            if data.get(field) is not None and isinstance(data[field], Decimal):
                data[field] = float(data[field])
        return data


class ResourceCreateSchema(Schema):
    """Schema for creating a new resource."""

    ms_project_uid = fields.Raw(validate=_validate_ms_project_uid, allow_none=True)
    name = fields.String(required=True, validate=Length(min=1, max=255))
    type = fields.String(
        validate=OneOf(["labor", "material", "cost"]), load_default="labor"
    )
    standard_rate = fields.Decimal(
        allow_none=False, places=2, validate=Range(min=0), load_default=0
    )
    overtime_rate = fields.Decimal(
        allow_none=False, places=2, validate=Range(min=0), load_default=0
    )
    email = fields.Email(required=True, validate=Length(max=255))
    is_active = fields.Boolean(load_default=True)

    @post_load
    def normalize_ms_project_uid(self, data: dict, **kwargs) -> dict:
        """Convert ms_project_uid numeric strings to integers.

        Handles both positive numeric strings. Negative values are rejected
        during validation, ensuring consistency between validation and normalization.
        """
        uid = data.get("ms_project_uid")
        if isinstance(uid, str) and uid.strip().isdigit():
            data["ms_project_uid"] = int(uid.strip())
        return data


class ResourceUpdateSchema(Schema):
    """Schema for partially updating a resource."""

    name = fields.String(validate=Length(min=1, max=255))
    standard_rate = fields.Decimal(allow_none=False, places=2, validate=Range(min=0))
    overtime_rate = fields.Decimal(allow_none=False, places=2, validate=Range(min=0))
    email = fields.Email(allow_none=True, validate=Length(max=255))
    is_active = fields.Boolean()

    @validates_schema
    def validate_non_empty(self, data: dict, **kwargs) -> None:
        """Ensure at least one field is provided for update."""
        if not data:
            raise ValidationError(
                "At least one field must be provided for update",
                field_name="_schema",
            )


class ResourceListResponseSchema(Schema):
    """Schema for paginated resource list response."""

    data = fields.List(fields.Nested(ResourceSchema), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)


class ResourceResponseSchema(Schema):
    """Schema for single resource response."""

    data = fields.Nested(ResourceSchema, required=True)
    message = fields.String()
