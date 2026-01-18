"""Statistics API schemas.

This module defines Marshmallow schemas for statistics endpoints,
including expense breakdowns, labor distribution, and monthly trends.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from marshmallow import Schema, fields, validate


class ExpenseBreakdownItemSchema(Schema):
    """Schema for a single expense category breakdown item.

    Attributes:
        category: Expense category (labor, procurement, subcontracting, overhead).
        amount: Total amount for this category.
        percentage: Percentage of total expenses.
        count: Number of expense records in this category.
    """

    category = fields.Str(
        required=True,
        validate=validate.OneOf(["labor", "procurement", "subcontracting", "overhead"]),
    )
    amount = fields.Float(required=True)
    percentage = fields.Float(required=True)
    count = fields.Int()


class EChartsSeriesDataItemSchema(Schema):
    """Schema for a single data point in ECharts series.

    Attributes:
        value: Numeric value.
        name: Label/name for this data point.
    """

    value = fields.Float(required=True)
    name = fields.Str(required=True)


class EChartsPieSeriesSchema(Schema):
    """Schema for ECharts pie chart series configuration.

    Attributes:
        name: Series name.
        type: Chart type (pie).
        radius: Pie/donut radius configuration.
        data: Array of data points.
    """

    name = fields.Str(required=True)
    type = fields.Str(required=True)
    radius = fields.List(fields.Str())
    data = fields.List(fields.Nested(EChartsSeriesDataItemSchema), required=True)


class ExpenseBreakdownEChartsFormatSchema(Schema):
    """Schema for ECharts-compatible pie chart configuration.

    Attributes:
        series: Array of pie chart series.
    """

    series = fields.List(fields.Nested(EChartsPieSeriesSchema))


class ExpenseBreakdownDataSchema(Schema):
    """Schema for expense breakdown data payload.

    Attributes:
        project_id: Project UUID.
        start_date: Filter start date.
        end_date: Filter end date.
        total_expenses: Total expenses across all categories.
        breakdown: Array of category breakdowns.
        echarts_format: ECharts-compatible configuration.
    """

    project_id = fields.UUID(required=True)
    start_date = fields.DateTime(allow_none=True)
    end_date = fields.DateTime(allow_none=True)
    total_expenses = fields.Float(required=True)
    breakdown = fields.List(fields.Nested(ExpenseBreakdownItemSchema), required=True)
    echarts_format = fields.Nested(ExpenseBreakdownEChartsFormatSchema)


class ExpenseBreakdownResponseSchema(Schema):
    """Response schema for expense breakdown endpoint.

    Attributes:
        data: Expense breakdown data envelope.
    """

    data = fields.Nested(ExpenseBreakdownDataSchema, required=True)


class LaborBreakdownItemSchema(Schema):
    """Schema for a single resource labor breakdown item.

    Attributes:
        resource_id: Resource UUID.
        resource_name: Resource name.
        amount: Total labor cost for this resource.
        percentage: Percentage of total labor cost.
        hours: Total hours worked.
        average_rate: Average hourly rate.
    """

    resource_id = fields.UUID(required=True)
    resource_name = fields.Str(required=True)
    amount = fields.Float(required=True)
    percentage = fields.Float(required=True)
    hours = fields.Float()
    average_rate = fields.Float()


class EChartsAxisSchema(Schema):
    """Schema for ECharts axis configuration.

    Attributes:
        type: Axis type (category, value).
        name: Axis name/label.
        data: Axis data (for category axes).
    """

    type = fields.Str(
        required=True,
        data_key="type",
        validate=validate.OneOf(["category", "value"]),
    )
    name = fields.Str()
    data = fields.List(fields.Str())


class EChartsLaborSeriesSchema(Schema):
    """Schema for ECharts bar chart series for labor data.

    Attributes:
        name: Series name.
        type: Chart type (bar).
        data: Array of numeric values.
    """

    name = fields.Str(required=True)
    type = fields.Str(required=True, validate=validate.OneOf(["bar"]))
    data = fields.List(fields.Float(), required=True)


class EChartsMonthlySeriesSchema(Schema):
    """Schema for ECharts series in monthly expense charts.

    Attributes:
        name: Series name.
        type: Chart type (bar or line).
        stack: Stack group identifier for stacked bars.
        data: Array of numeric values.
    """

    name = fields.Str(
        required=True,
        validate=validate.OneOf(["Labor", "Subcontracting", "Procurement", "Overhead"]),
    )
    type = fields.Str(required=True, validate=validate.OneOf(["bar", "line"]))
    stack = fields.Str()
    data = fields.List(fields.Float(), required=True)


class LaborByResourceEChartsFormatSchema(Schema):
    """Schema for ECharts-compatible bar chart configuration.

    Attributes:
        xAxis: X-axis configuration (camelCase for ECharts).
        yAxis: Y-axis configuration (camelCase for ECharts).
        series: Array of bar chart series.
    """

    xAxis = fields.Nested(EChartsAxisSchema)  # noqa: N815
    yAxis = fields.Nested(EChartsAxisSchema)  # noqa: N815
    series = fields.List(fields.Nested(EChartsLaborSeriesSchema))


class LaborByResourceDataSchema(Schema):
    """Schema for labor by resource data payload.

    Attributes:
        project_id: Project UUID.
        total_labor_cost: Total labor cost across all resources.
        resource_count: Total number of resources.
        breakdown: Array of resource breakdowns.
        echarts_format: ECharts-compatible configuration.
    """

    project_id = fields.UUID(required=True)
    total_labor_cost = fields.Float(required=True)
    resource_count = fields.Int(required=True)
    breakdown = fields.List(fields.Nested(LaborBreakdownItemSchema), required=True)
    echarts_format = fields.Nested(LaborByResourceEChartsFormatSchema)


class LaborByResourceResponseSchema(Schema):
    """Response schema for labor by resource endpoint.

    Attributes:
        data: Labor by resource data envelope.
    """

    data = fields.Nested(LaborByResourceDataSchema, required=True)


class MonthlyExpensesItemSchema(Schema):
    """Schema for a single month's expense data.

    Attributes:
        month: Month in YYYY-MM format.
        total: Total expenses for the month.
        labor: Labor expenses.
        subcontracting: Subcontracting expenses.
        procurement: Procurement expenses.
        overhead: Overhead expenses.
    """

    month = fields.Str(
        required=True,
        validate=validate.Regexp(r"^\d{4}-\d{2}$"),
    )
    total = fields.Float(required=True)
    labor = fields.Float()
    subcontracting = fields.Float()
    procurement = fields.Float()
    overhead = fields.Float()


class MonthlyExpensesEChartsFormatSchema(Schema):
    """Schema for ECharts-compatible stacked bar chart configuration.

    Attributes:
        xAxis: X-axis configuration (camelCase for ECharts).
        yAxis: Y-axis configuration (camelCase for ECharts).
        series: Array of stacked bar/line series.
    """

    xAxis = fields.Nested(EChartsAxisSchema)  # noqa: N815
    yAxis = fields.Nested(EChartsAxisSchema)  # noqa: N815
    series = fields.List(fields.Nested(EChartsMonthlySeriesSchema))


class MonthlyExpensesDataSchema(Schema):
    """Schema for monthly expenses data payload.

    Attributes:
        project_id: Project UUID.
        start_date: Period start date.
        end_date: Period end date.
        cumulative: Whether values are cumulative.
        monthly_data: Array of monthly expense data.
        echarts_format: ECharts-compatible configuration.
    """

    project_id = fields.UUID(required=True)
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    cumulative = fields.Bool()
    monthly_data = fields.List(fields.Nested(MonthlyExpensesItemSchema), required=True)
    echarts_format = fields.Nested(MonthlyExpensesEChartsFormatSchema)


class MonthlyExpensesResponseSchema(Schema):
    """Response schema for monthly expenses endpoint.

    Attributes:
        data: Monthly expenses data envelope.
    """

    data = fields.Nested(MonthlyExpensesDataSchema, required=True)
