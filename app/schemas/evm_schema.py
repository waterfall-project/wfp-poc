# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Marshmallow schemas for EVM endpoints.

Defines validation and serialization schemas for EVM indicators,
time series, and forecast responses following the OpenAPI contract.
"""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validates_schema
from marshmallow.validate import OneOf

EV_METHOD_VALUES = ["physical", "milestone", "both"]
TIME_SERIES_METHOD_VALUES = ["physical", "milestone"]
TIME_SERIES_GRANULARITY_VALUES = ["month", "week", "day"]


class EVMIndicatorsQuerySchema(Schema):
    """Schema for EVM indicators query parameters."""

    as_of_date = fields.DateTime(load_default=None)
    ev_method = fields.String(load_default="both", validate=OneOf(EV_METHOD_VALUES))


class EVMIndicatorsSchema(Schema):
    """Schema for EVM indicators response."""

    project_id = fields.UUID(required=True)
    as_of_date = fields.DateTime(required=True)
    bac = fields.Float(allow_none=True)
    pv = fields.Float(allow_none=True)
    ac = fields.Float(allow_none=True)
    ev_physical = fields.Float(allow_none=True)
    ev_milestone = fields.Float(allow_none=True)
    cv_physical = fields.Float(allow_none=True)
    sv_physical = fields.Float(allow_none=True)
    cpi_physical = fields.Float(allow_none=True)
    spi_physical = fields.Float(allow_none=True)
    eac_cpi_physical = fields.Float(allow_none=True)
    etc_physical = fields.Float(allow_none=True)
    vac_physical = fields.Float(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesQuerySchema(Schema):
    """Schema for EVM time series query parameters."""

    start_date = fields.DateTime(load_default=None)
    end_date = fields.DateTime(load_default=None)
    granularity = fields.String(
        load_default="month", validate=OneOf(TIME_SERIES_GRANULARITY_VALUES)
    )
    ev_method = fields.String(
        load_default="physical", validate=OneOf(TIME_SERIES_METHOD_VALUES)
    )
    cumulative = fields.Boolean(load_default=True)

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


class EVMTimeSeriesDataSchema(Schema):
    """Schema for EVM time series data arrays."""

    dates = fields.List(fields.Date(), required=True)
    pv = fields.List(fields.Float(), required=True)
    ac = fields.List(fields.Float(), required=True)
    ev = fields.List(fields.Float(), required=True)


class EVMTimeSeriesSchema(Schema):
    """Schema for EVM time series response."""

    project_id = fields.UUID(required=True)
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    granularity = fields.String(required=True)
    data = fields.Nested(EVMTimeSeriesDataSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastMethodSchema(Schema):
    """Schema for a single EVM forecast method entry."""

    eac = fields.Float(allow_none=True)
    etc = fields.Float(allow_none=True)
    vac = fields.Float(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsMethodsSchema(Schema):
    """Schema for EVM forecast methods container."""

    cpi_method = fields.Nested(EVMForecastMethodSchema, required=True)
    cpi_spi_method = fields.Nested(EVMForecastMethodSchema, required=True)
    plan_based = fields.Nested(EVMForecastMethodSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsSchema(Schema):
    """Schema for EVM forecasts response."""

    project_id = fields.UUID(required=True)
    as_of_date = fields.DateTime(required=True)
    bac = fields.Float(allow_none=True)
    ac = fields.Float(allow_none=True)
    forecasts = fields.Nested(EVMForecastsMethodsSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsQuerySchema(Schema):
    """Schema for EVM forecasts query parameters."""

    as_of_date = fields.DateTime(load_default=None)
    ev_method = fields.String(load_default="physical", validate=OneOf(EV_METHOD_VALUES))
