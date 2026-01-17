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
    calculation_timestamp = fields.DateTime(required=True)
    bac = fields.Float(allow_none=True)
    pv = fields.Float(allow_none=True)
    ac = fields.Float(allow_none=True)
    ev_physical = fields.Float(allow_none=True)
    ev_milestone = fields.Float(allow_none=True)
    cv_physical = fields.Float(allow_none=True)
    cv_milestone = fields.Float(allow_none=True)
    sv_physical = fields.Float(allow_none=True)
    sv_milestone = fields.Float(allow_none=True)
    cpi_physical = fields.Float(allow_none=True)
    cpi_milestone = fields.Float(allow_none=True)
    spi_physical = fields.Float(allow_none=True)
    spi_milestone = fields.Float(allow_none=True)
    eac_cpi_physical = fields.Float(allow_none=True)
    eac_cpi_milestone = fields.Float(allow_none=True)
    eac_cpi_spi_physical = fields.Float(allow_none=True)
    eac_cpi_spi_milestone = fields.Float(allow_none=True)
    eac_plan_based = fields.Float(allow_none=True)
    etc_cpi_physical = fields.Float(allow_none=True)
    etc_cpi_milestone = fields.Float(allow_none=True)
    etc_cpi_spi_physical = fields.Float(allow_none=True)
    etc_cpi_spi_milestone = fields.Float(allow_none=True)
    etc_plan_based = fields.Float(allow_none=True)
    vac_cpi_physical = fields.Float(allow_none=True)
    vac_cpi_milestone = fields.Float(allow_none=True)
    vac_cpi_spi_physical = fields.Float(allow_none=True)
    vac_cpi_spi_milestone = fields.Float(allow_none=True)
    vac_plan_based = fields.Float(allow_none=True)
    etc_physical = fields.Float(allow_none=True, metadata={"deprecated": True})
    vac_physical = fields.Float(allow_none=True, metadata={"deprecated": True})
    percent_complete_physical = fields.Float(allow_none=True)
    percent_complete_milestone = fields.Float(allow_none=True)

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


class EVMTimeSeriesPointSchema(Schema):
    """Schema for a single EVM time series data point."""

    date = fields.DateTime(required=True)
    pv = fields.Float(required=True)
    ac = fields.Float(required=True)
    ev = fields.Float(required=True)
    cv = fields.Float(allow_none=True)
    sv = fields.Float(allow_none=True)
    cpi = fields.Float(allow_none=True)
    spi = fields.Float(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesEChartsAxisSchema(Schema):
    """Schema for ECharts xAxis configuration."""

    type = fields.String(required=True)
    data = fields.List(fields.String(), required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesEChartsSeriesSchema(Schema):
    """Schema for ECharts series entries."""

    name = fields.String(required=True)
    type = fields.String(required=True)
    data = fields.List(fields.Float(), required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesEChartsFormatSchema(Schema):
    """Schema for ECharts format wrapper."""

    x_axis = fields.Nested(
        EVMTimeSeriesEChartsAxisSchema,
        required=True,
        data_key="xAxis",
    )
    series = fields.List(fields.Nested(EVMTimeSeriesEChartsSeriesSchema), required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesSchema(Schema):
    """Schema for EVM time series response."""

    project_id = fields.UUID(required=True)
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    granularity = fields.String(required=True)
    ev_method = fields.String(required=True)
    cumulative = fields.Boolean(required=True)
    series = fields.List(fields.Nested(EVMTimeSeriesPointSchema), required=True)
    echarts_format = fields.Nested(EVMTimeSeriesEChartsFormatSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastItemSchema(Schema):
    """Schema for a single EVM forecast item."""

    method = fields.String(
        required=True, validate=OneOf(["cpi", "cpi_spi", "plan_based"])
    )
    description = fields.String(required=True)
    formula = fields.String(required=True)
    eac = fields.Float(required=True)
    etc = fields.Float(required=True)
    vac = fields.Float(required=True)
    confidence = fields.String(required=True, validate=OneOf(["low", "medium", "high"]))
    use_case = fields.String(required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsSchema(Schema):
    """Schema for EVM forecasts response."""

    project_id = fields.UUID(required=True)
    as_of_date = fields.DateTime(required=True)
    bac = fields.Float(allow_none=True, required=True)
    current_ac = fields.Float(allow_none=True, required=True)
    current_ev = fields.Float(allow_none=True, required=True)
    current_pv = fields.Float(allow_none=True, required=True)
    remaining_pv = fields.Float(allow_none=True, required=True)
    cpi = fields.Float(allow_none=True)
    spi = fields.Float(allow_none=True)
    forecasts = fields.List(fields.Nested(EVMForecastItemSchema), required=True)
    recommended_method = fields.String(allow_none=True)
    recommendation_reason = fields.String(allow_none=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsQuerySchema(Schema):
    """Schema for EVM forecasts query parameters."""

    as_of_date = fields.DateTime(load_default=None)
    ev_method = fields.String(load_default="physical", validate=OneOf(EV_METHOD_VALUES))


class EVMIndicatorsResponseSchema(Schema):
    """Schema wrapper for EVM indicators responses."""

    data = fields.Nested(EVMIndicatorsSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMTimeSeriesResponseSchema(Schema):
    """Schema wrapper for EVM time series responses."""

    data = fields.Nested(EVMTimeSeriesSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True


class EVMForecastsResponseSchema(Schema):
    """Schema wrapper for EVM forecasts responses."""

    data = fields.Nested(EVMForecastsSchema, required=True)

    class Meta:
        """Schema configuration."""

        ordered = True
