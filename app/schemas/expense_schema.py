# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for Expense entity.

Defines validation and serialization schemas for expense CRUD and bulk import
operations, aligned with the OpenAPI contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from marshmallow import Schema, ValidationError, fields, post_dump, validates_schema
from marshmallow.validate import Length, OneOf, Range

EXPENSE_CATEGORIES = ["labor", "procurement", "subcontracting", "overhead"]


class ExpenseSchema(Schema):
    """Base schema for expense serialization."""

    id = fields.UUID(dump_only=True)
    project_id = fields.UUID(dump_only=True)
    milestone_id = fields.UUID(allow_none=True)
    resource_id = fields.UUID(allow_none=True)
    date = fields.DateTime(required=True)
    amount = fields.Decimal(required=True, as_string=True, places=2)
    category = fields.String(required=True, validate=OneOf(EXPENSE_CATEGORIES))
    description = fields.String(validate=Length(max=500), allow_none=True)
    reference_number = fields.String(validate=Length(max=50), allow_none=True)
    purchase_document = fields.String(validate=Length(max=50), allow_none=True)
    fiscal_year = fields.Integer(allow_none=True)
    period = fields.Integer(validate=Range(min=1, max=12), allow_none=True)
    otp_element = fields.String(validate=Length(max=50), allow_none=True)
    accounting_nature = fields.String(validate=Length(max=50), allow_none=True)
    vendor_name = fields.String(validate=Length(max=255), allow_none=True)
    origin_group = fields.String(validate=Length(max=50), allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    class Meta:
        """Schema configuration."""

        ordered = True

    @post_dump
    def convert_decimal_amount(
        self, data: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        """Convert Decimal amount to float for JSON responses."""
        if "amount" in data and isinstance(data["amount"], Decimal):
            data["amount"] = float(data["amount"])
        return data


class ExpenseCreateSchema(Schema):
    """Schema for creating an expense."""

    resource_id = fields.UUID(allow_none=True)
    date = fields.DateTime(required=True)
    amount = fields.Decimal(
        required=True, as_string=True, places=2, validate=Range(min=0)
    )
    category = fields.String(required=True, validate=OneOf(EXPENSE_CATEGORIES))
    description = fields.String(validate=Length(max=500), allow_none=True)
    reference_number = fields.String(validate=Length(max=50), allow_none=True)
    purchase_document = fields.String(validate=Length(max=50), allow_none=True)
    fiscal_year = fields.Integer(allow_none=True)
    period = fields.Integer(validate=Range(min=1, max=12), allow_none=True)
    otp_element = fields.String(validate=Length(max=50), allow_none=True)
    accounting_nature = fields.String(validate=Length(max=50), allow_none=True)
    vendor_name = fields.String(validate=Length(max=255), allow_none=True)
    origin_group = fields.String(validate=Length(max=50), allow_none=True)


class ExpenseUpdateSchema(Schema):
    """Schema for partial expense updates."""

    date = fields.DateTime()
    amount = fields.Decimal(as_string=True, places=2, validate=Range(min=0))
    category = fields.String(validate=OneOf(EXPENSE_CATEGORIES))
    description = fields.String(validate=Length(max=500))

    @validates_schema
    def validate_non_empty(self, data: dict[str, Any], **kwargs: Any) -> None:
        """Ensure at least one field is provided for update."""
        if not data:
            raise ValidationError(
                "At least one field must be provided for update",
                field_name="_schema",
            )


class ExpenseResponseSchema(Schema):
    """Schema for expense response wrapper."""

    data = fields.Nested(ExpenseSchema(), required=True)
    message = fields.String(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class ExpenseListResponseSchema(Schema):
    """Schema for paginated expense list response."""

    data = fields.List(fields.Nested(ExpenseSchema()), required=True)
    page = fields.Integer(required=True)
    per_page = fields.Integer(required=True)
    total = fields.Integer(required=True)
    total_pages = fields.Integer(required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class ExpenseBulkCreateSchema(Schema):
    """Schema for bulk expense creation payload."""

    expenses = fields.List(
        fields.Nested(ExpenseCreateSchema()),
        required=True,
        validate=Length(min=1, max=1000),
    )


class ExpenseBulkErrorSchema(Schema):
    """Schema for bulk expense error entries."""

    index = fields.Integer(required=True)
    error = fields.String(required=True)


class ExpenseBulkDataSchema(Schema):
    """Schema for bulk expense response data."""

    created_count = fields.Integer(required=True)
    failed_count = fields.Integer(required=True)
    expenses = fields.List(fields.Nested(ExpenseSchema()))
    errors = fields.List(fields.Nested(ExpenseBulkErrorSchema()))

    class Meta:
        """Schema configuration."""

        ordered = True


class ExpenseBulkResponseSchema(Schema):
    """Schema for bulk expense response wrapper."""

    data = fields.Nested(ExpenseBulkDataSchema(), required=True)
    message = fields.String(required=True)

    class Meta:
        """Schema configuration."""

        ordered = True
