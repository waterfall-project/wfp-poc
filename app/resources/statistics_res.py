"""Statistics API resources.

This module provides REST resources for project statistics endpoints,
including expense breakdowns, labor distribution, and monthly trends.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from flask import request
from flask_restful import Resource
from sqlalchemy import case, func

from app import db, limiter
from app.models.assignment import Assignment
from app.models.expense import Expense
from app.models.project import Project
from app.models.resource import Resource as ResourceModel
from app.schemas.statistics_schema import (
    ExpenseBreakdownResponseSchema,
    LaborByResourceResponseSchema,
    MonthlyExpensesResponseSchema,
)
from app.services.guardian_service import Operation
from app.utils.jwt_decorators import access_required, require_jwt_auth
from app.utils.rate_limit import rate_limit_user_key

DictStrAny = dict[str, Any]


class ExpenseByCategoryResource(Resource):
    """REST resource for expense breakdown by category.

    This resource handles GET /projects/{project_id}/statistics/expenses/by-category
    endpoint for retrieving pie chart data of expenses by category.

    Attributes:
        response_schema: Marshmallow schema for response validation.
    """

    def __init__(self) -> None:
        """Initialize the resource with response schema."""
        self.response_schema = ExpenseBreakdownResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "statistics")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str) -> tuple[DictStrAny, int]:
        """Retrieve expense breakdown by category for a project.

        Args:
            project_id: Project UUID from URL path.

        Query Parameters:
            start_date: Optional filter from date (ISO 8601).
            end_date: Optional filter to date (ISO 8601).
            milestone_id: Optional filter by milestone UUID.

        Returns:
            Tuple of (response dict, status code).

        Raises:
            NotFoundError: If project does not exist.
            ValidationError: If query parameters are invalid.

        Examples:
            >>> resource.get(project_id="a1b2c3d4-...")
            ({'data': {'project_id': '...', 'total_expenses': 820000.0, ...}}, 200)
        """
        # Validate project exists and user has access
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return {"error": "Project not found"}, 404

        # Parse query parameters
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        milestone_id_str = request.args.get("milestone_id")

        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None
        milestone_id = UUID(milestone_id_str) if milestone_id_str else None

        # Build query
        query = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label("amount"),
            func.count(Expense.id).label("count"),
        ).filter(Expense.project_id == UUID(project_id))

        if start_date:
            query = query.filter(Expense.date >= start_date)
        if end_date:
            query = query.filter(Expense.date <= end_date)
        if milestone_id:
            query = query.filter(Expense.milestone_id == milestone_id)

        query = query.group_by(Expense.category)
        results = query.all()

        # Calculate totals and percentages
        total_expenses = sum(float(r.amount) for r in results)

        breakdown = []
        echarts_data = []

        for row in results:
            amount = float(row.amount)
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0.0

            breakdown.append(
                {
                    "category": row.category,
                    "amount": amount,
                    "percentage": round(percentage, 2),
                    "count": row.count,
                }
            )

            echarts_data.append(
                {
                    "value": amount,
                    "name": f"{row.category.capitalize()} ({percentage:.2f}%)",
                }
            )

        # Sort breakdown by amount descending
        breakdown.sort(key=lambda x: x["amount"], reverse=True)

        # Build response
        data: DictStrAny = {
            "project_id": project_id,
            "total_expenses": round(total_expenses, 2),
            "breakdown": breakdown,
        }

        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date

        # Add ECharts format
        if echarts_data:
            data["echarts_format"] = {
                "series": [
                    {
                        "name": "Expenses by Category",
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "data": echarts_data,
                    }
                ]
            }

        return self.response_schema.dump({"data": data}), 200


class LaborByResourceResource(Resource):
    """REST resource for labor cost by resource.

    This resource handles GET /projects/{project_id}/statistics/labor/by-resource
    endpoint for retrieving labor cost distribution by resource.

    Attributes:
        response_schema: Marshmallow schema for response validation.
    """

    def __init__(self) -> None:
        """Initialize the resource with response schema."""
        self.response_schema = LaborByResourceResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "statistics")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str) -> tuple[DictStrAny, int]:
        """Retrieve labor cost breakdown by resource for a project.

        Args:
            project_id: Project UUID from URL path.

        Query Parameters:
            start_date: Optional filter from date (ISO 8601).
            end_date: Optional filter to date (ISO 8601).
            limit: Max resources to return (1-100, default 20).
            sort_order: Sort order (asc/desc, default desc).

        Returns:
            Tuple of (response dict, status code).

        Raises:
            NotFoundError: If project does not exist.
            ValidationError: If query parameters are invalid.

        Examples:
            >>> resource.get(project_id="a1b2c3d4-...")
            ({'data': {'project_id': '...', 'total_labor_cost': 450000.0, ...}}, 200)
        """
        # Validate project exists
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return {"error": "Project not found"}, 404

        # Parse query parameters
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        limit = int(request.args.get("limit", "20"))
        sort_order = request.args.get("sort_order", "desc")

        # Validate limit
        if limit < 1 or limit > 100:
            return {"error": "Limit must be between 1 and 100"}, 400

        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

        # Query assignments with labor costs
        query = (
            db.session.query(
                Assignment.resource_id,
                ResourceModel.name.label("resource_name"),
                func.sum(Assignment.actual_cost).label("amount"),
                func.sum(Assignment.actual_work_minutes / 60.0).label("hours"),
            )
            .join(ResourceModel, Assignment.resource_id == ResourceModel.id)
            .filter(Assignment.project_id == UUID(project_id))
            .filter(Assignment.actual_cost.isnot(None))
            .filter(Assignment.actual_cost > 0)
        )

        # Apply date filters (assuming we filter by task dates)
        if start_date or end_date:
            from app.models.task import Task

            query = query.join(Task, Assignment.task_id == Task.id)
            if start_date:
                query = query.filter(Task.actual_start_date >= start_date)
            if end_date:
                query = query.filter(Task.actual_finish_date <= end_date)

        query = query.group_by(Assignment.resource_id, ResourceModel.name)

        # Sort by amount
        if sort_order == "asc":
            query = query.order_by(func.sum(Assignment.actual_cost).asc())
        else:
            query = query.order_by(func.sum(Assignment.actual_cost).desc())

        query = query.limit(limit)
        results = query.all()

        # Calculate total labor cost for percentages
        total_labor_cost = sum(float(r.amount) for r in results)
        resource_count = len(results)

        breakdown = []
        echarts_names = []
        echarts_values = []

        for row in results:
            amount = float(row.amount)
            hours = float(row.hours) if row.hours else 0.0
            percentage = (
                (amount / total_labor_cost * 100) if total_labor_cost > 0 else 0.0
            )
            average_rate = (amount / hours) if hours > 0 else 0.0

            breakdown.append(
                {
                    "resource_id": str(row.resource_id),
                    "resource_name": row.resource_name,
                    "amount": round(amount, 2),
                    "percentage": round(percentage, 2),
                    "hours": round(hours, 1),
                    "average_rate": round(average_rate, 2),
                }
            )

            echarts_names.append(row.resource_name)
            echarts_values.append(round(amount, 2))

        # Build response
        data: DictStrAny = {
            "project_id": project_id,
            "total_labor_cost": round(total_labor_cost, 2),
            "resource_count": resource_count,
            "breakdown": breakdown,
        }

        # Add ECharts format
        if echarts_names:
            data["echarts_format"] = {
                "xAxis": {"type": "category", "data": echarts_names},
                "yAxis": {"type": "value", "name": "Cost (€)"},
                "series": [
                    {"name": "Labor Cost", "type": "bar", "data": echarts_values}
                ],
            }

        return self.response_schema.dump({"data": data}), 200


class MonthlyExpensesResource(Resource):
    """REST resource for monthly expense distribution.

    This resource handles GET /projects/{project_id}/statistics/expenses/monthly
    endpoint for retrieving monthly expense trends.

    Attributes:
        response_schema: Marshmallow schema for response validation.
    """

    def __init__(self) -> None:
        """Initialize the resource with response schema."""
        self.response_schema = MonthlyExpensesResponseSchema()

    @require_jwt_auth
    @access_required(Operation.READ, "statistics")
    @limiter.limit("100 per minute", key_func=rate_limit_user_key)
    def get(self, project_id: str) -> tuple[DictStrAny, int]:
        """Retrieve monthly expense distribution for a project.

        Args:
            project_id: Project UUID from URL path.

        Query Parameters:
            start_date: Optional filter from date (ISO 8601).
            end_date: Optional filter to date (ISO 8601).
            category: Optional filter by expense category.
            cumulative: Whether to return cumulative values (default false).

        Returns:
            Tuple of (response dict, status code).

        Raises:
            NotFoundError: If project does not exist.
            ValidationError: If query parameters are invalid.

        Examples:
            >>> resource.get(project_id="a1b2c3d4-...")
            ({'data': {'project_id': '...', 'monthly_data': [...]}}, 200)
        """
        # Validate project exists
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return {"error": "Project not found"}, 404

        # Parse query parameters
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        category = request.args.get("category")
        cumulative = request.args.get("cumulative", "false").lower() == "true"

        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

        # Validate category if provided
        valid_categories = ["labor", "procurement", "subcontracting", "overhead"]
        if category and category not in valid_categories:
            return {
                "error": f"Invalid category. Must be one of: {valid_categories}"
            }, 400

        # Query expenses by month and category
        month_expr = func.strftime("%Y-%m", Expense.date)

        # Base query
        if category:
            # Single category query
            query = (
                db.session.query(
                    month_expr.label("month"),
                    func.sum(Expense.amount).label("total"),
                )
                .filter(Expense.project_id == UUID(project_id))
                .filter(Expense.category == category)
            )
        else:
            # All categories query with pivoting
            query = db.session.query(
                month_expr.label("month"),
                func.sum(Expense.amount).label("total"),
                func.sum(
                    case((Expense.category == "labor", Expense.amount), else_=0)
                ).label("labor"),
                func.sum(
                    case(
                        (Expense.category == "subcontracting", Expense.amount),
                        else_=0,
                    )
                ).label("subcontracting"),
                func.sum(
                    case((Expense.category == "procurement", Expense.amount), else_=0)
                ).label("procurement"),
                func.sum(
                    case((Expense.category == "overhead", Expense.amount), else_=0)
                ).label("overhead"),
            ).filter(Expense.project_id == UUID(project_id))

        # Apply date filters
        if start_date:
            query = query.filter(Expense.date >= start_date)
        if end_date:
            query = query.filter(Expense.date <= end_date)

        query = query.group_by(month_expr).order_by(month_expr)
        results = query.all()

        # Build monthly data
        monthly_data = []
        cumulative_total = 0.0
        cumulative_labor = 0.0
        cumulative_subcontracting = 0.0
        cumulative_procurement = 0.0
        cumulative_overhead = 0.0

        for row in results:
            total = float(row.total)

            if cumulative:
                cumulative_total += total
                month_total = cumulative_total
            else:
                month_total = total

            month_item: DictStrAny = {
                "month": row.month,
                "total": round(month_total, 2),
            }

            if not category:
                # Add category breakdowns
                labor = float(row.labor) if hasattr(row, "labor") else 0.0
                subcontracting = (
                    float(row.subcontracting) if hasattr(row, "subcontracting") else 0.0
                )
                procurement = (
                    float(row.procurement) if hasattr(row, "procurement") else 0.0
                )
                overhead = float(row.overhead) if hasattr(row, "overhead") else 0.0

                if cumulative:
                    cumulative_labor += labor
                    cumulative_subcontracting += subcontracting
                    cumulative_procurement += procurement
                    cumulative_overhead += overhead

                    month_item["labor"] = round(cumulative_labor, 2)
                    month_item["subcontracting"] = round(cumulative_subcontracting, 2)
                    month_item["procurement"] = round(cumulative_procurement, 2)
                    month_item["overhead"] = round(cumulative_overhead, 2)
                else:
                    month_item["labor"] = round(labor, 2)
                    month_item["subcontracting"] = round(subcontracting, 2)
                    month_item["procurement"] = round(procurement, 2)
                    month_item["overhead"] = round(overhead, 2)

            monthly_data.append(month_item)

        # Build ECharts format
        echarts_months = [item["month"] for item in monthly_data]
        echarts_series = []

        if category:
            # Single category
            echarts_series.append(
                {
                    "name": category.capitalize(),
                    "type": "bar",
                    "data": [item["total"] for item in monthly_data],
                }
            )
        else:
            # Stacked bars for all categories
            echarts_series = [
                {
                    "name": "Labor",
                    "type": "bar",
                    "stack": "total",
                    "data": [item.get("labor", 0.0) for item in monthly_data],
                },
                {
                    "name": "Subcontracting",
                    "type": "bar",
                    "stack": "total",
                    "data": [item.get("subcontracting", 0.0) for item in monthly_data],
                },
                {
                    "name": "Procurement",
                    "type": "bar",
                    "stack": "total",
                    "data": [item.get("procurement", 0.0) for item in monthly_data],
                },
                {
                    "name": "Overhead",
                    "type": "bar",
                    "stack": "total",
                    "data": [item.get("overhead", 0.0) for item in monthly_data],
                },
            ]

        # Build response
        data: DictStrAny = {
            "project_id": project_id,
            "cumulative": cumulative,
            "monthly_data": monthly_data,
        }

        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date

        # Add ECharts format
        if echarts_months:
            data["echarts_format"] = {
                "xAxis": {"type": "category", "data": echarts_months},
                "yAxis": {"type": "value", "name": "Expenses (€)"},
                "series": echarts_series,
            }

        return self.response_schema.dump({"data": data}), 200
