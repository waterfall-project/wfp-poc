"""Integration tests for statistics API endpoints.

This module provides integration tests for all statistics endpoints,
testing the complete request-response cycle with real database.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.assignment import Assignment
from app.models.expense import Expense
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task


@pytest.fixture
def test_project(app: Flask) -> Project:
    """Create a test project for integration tests.

    Args:
        app: Flask application instance.

    Returns:
        Created project instance.
    """
    from app import db

    with app.app_context():
        project = Project(
            id=uuid4(),
            name="Statistics Test Project",
            company_id=uuid4(),
            start_date=datetime(2024, 11, 1, tzinfo=UTC),
            finish_date=datetime(2026, 12, 31, tzinfo=UTC),
            budget=Decimal("1000000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def test_expenses(app: Flask, test_project: Project) -> list[Expense]:
    """Create test expenses for integration tests.

    Args:
        app: Flask application instance.
        test_project: Test project.

    Returns:
        List of created expense instances.
    """
    from app import db

    with app.app_context():
        expenses = [
            Expense(
                id=uuid4(),
                project_id=test_project.id,
                category="labor",
                date=datetime(2024, 11, 15, tzinfo=UTC),
                amount=Decimal("450000.00"),
            ),
            Expense(
                id=uuid4(),
                project_id=test_project.id,
                category="subcontracting",
                date=datetime(2024, 11, 20, tzinfo=UTC),
                amount=Decimal("220000.00"),
            ),
            Expense(
                id=uuid4(),
                project_id=test_project.id,
                category="procurement",
                date=datetime(2024, 12, 10, tzinfo=UTC),
                amount=Decimal("120000.00"),
            ),
            Expense(
                id=uuid4(),
                project_id=test_project.id,
                category="overhead",
                date=datetime(2024, 12, 15, tzinfo=UTC),
                amount=Decimal("30000.00"),
            ),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        for exp in expenses:
            db.session.refresh(exp)
        return expenses


@pytest.fixture
def test_resources(app: Flask, test_project: Project) -> list[Resource]:
    """Create test resources for labor statistics.

    Args:
        app: Flask application instance.
        test_project: Test project.

    Returns:
        List of created resource instances.
    """
    from app import db

    with app.app_context():
        resources = [
            Resource(
                id=uuid4(),
                company_id=test_project.company_id,
                name="Jean Dupont",
                standard_rate=85.00,
            ),
            Resource(
                id=uuid4(),
                company_id=test_project.company_id,
                name="Marie Martin",
                standard_rate=80.00,
            ),
        ]
        db.session.add_all(resources)
        db.session.commit()
        for res in resources:
            db.session.refresh(res)
        return resources


@pytest.fixture
def test_tasks(app: Flask, test_project: Project) -> list[Task]:
    """Create test tasks for assignments.

    Args:
        app: Flask application instance.
        test_project: Test project.

    Returns:
        List of created task instances.
    """
    from app import db

    with app.app_context():
        tasks = [
            Task(
                id=uuid4(),
                project_id=test_project.id,
                name="Development Task",
                wbs_code="1",
                actual_start_date=datetime(2024, 11, 1, tzinfo=UTC),
                actual_finish_date=datetime(2024, 11, 30, tzinfo=UTC),
            ),
        ]
        db.session.add_all(tasks)
        db.session.commit()
        for task in tasks:
            db.session.refresh(task)
        return tasks


@pytest.fixture
def test_assignments(
    app: Flask,
    test_project: Project,
    test_resources: list[Resource],
    test_tasks: list[Task],
) -> list[Assignment]:
    """Create test assignments for labor statistics.

    Args:
        app: Flask application instance.
        test_project: Test project.
        test_resources: Test resources.
        test_tasks: Test tasks.

    Returns:
        List of created assignment instances.
    """
    from app import db

    with app.app_context():
        assignments = [
            Assignment(
                id=uuid4(),
                task_id=test_tasks[0].id,
                resource_id=test_resources[0].id,
                project_id=test_project.id,
                actual_work_minutes=60000,  # 1000 hours
                actual_cost=Decimal("85000.00"),
            ),
            Assignment(
                id=uuid4(),
                task_id=test_tasks[0].id,
                resource_id=test_resources[1].id,
                project_id=test_project.id,
                actual_work_minutes=54000,  # 900 hours
                actual_cost=Decimal("72000.00"),
            ),
        ]
        db.session.add_all(assignments)
        db.session.commit()
        for assignment in assignments:
            db.session.refresh(assignment)
        return assignments


class TestExpenseByCategoryAPI:
    """Integration tests for expense breakdown by category endpoint."""

    def test_get_expense_breakdown_integration(
        self,
        integration_client: FlaskClient,
        test_project: Project,
        test_expenses: list[Expense],
    ) -> None:
        """Test complete expense breakdown request-response cycle.

        Given: Project with expenses in database
        When: GET request is made to expense breakdown endpoint
        Then: Response contains correct breakdown and ECharts format
        """
        response = integration_client.get(
            f"/v0/projects/{test_project.id}/statistics/expenses/by-category"
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.json["data"]  # type: ignore[index]
        assert data["project_id"] == str(test_project.id)
        assert data["total_expenses"] == 820000.0

        # Verify breakdown structure
        breakdown = data["breakdown"]
        assert len(breakdown) == 4
        assert all("category" in item for item in breakdown)
        assert all("amount" in item for item in breakdown)
        assert all("percentage" in item for item in breakdown)

        # Verify ECharts format structure
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert "series" in echarts
        assert len(echarts["series"]) > 0
        assert echarts["series"][0]["type"] == "pie"


class TestLaborByResourceAPI:
    """Integration tests for labor by resource endpoint."""

    def test_get_labor_by_resource_integration(
        self,
        integration_client: FlaskClient,
        test_project: Project,
        test_assignments: list[Assignment],
    ) -> None:
        """Test complete labor by resource request-response cycle.

        Given: Project with assignments in database
        When: GET request is made to labor by resource endpoint
        Then: Response contains correct breakdown and ECharts format
        """
        response = integration_client.get(
            f"/v0/projects/{test_project.id}/statistics/labor/by-resource"
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.json["data"]  # type: ignore[index]
        assert data["project_id"] == str(test_project.id)
        assert data["total_labor_cost"] == 157000.0
        assert data["resource_count"] == 2

        # Verify breakdown structure
        breakdown = data["breakdown"]
        assert len(breakdown) == 2
        assert all("resource_id" in item for item in breakdown)
        assert all("resource_name" in item for item in breakdown)
        assert all("amount" in item for item in breakdown)
        assert all("hours" in item for item in breakdown)

        # Verify ECharts format structure
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert "xAxis" in echarts
        assert "yAxis" in echarts
        assert "series" in echarts
        assert echarts["series"][0]["type"] == "bar"


class TestMonthlyExpensesAPI:
    """Integration tests for monthly expenses endpoint."""

    def test_get_monthly_expenses_integration(
        self,
        integration_client: FlaskClient,
        test_project: Project,
        test_expenses: list[Expense],
    ) -> None:
        """Test complete monthly expenses request-response cycle.

        Given: Project with expenses across months in database
        When: GET request is made to monthly expenses endpoint
        Then: Response contains correct monthly data and ECharts format
        """
        response = integration_client.get(
            f"/v0/projects/{test_project.id}/statistics/expenses/monthly"
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.json["data"]  # type: ignore[index]
        assert data["project_id"] == str(test_project.id)
        assert "cumulative" in data

        # Verify monthly data structure
        monthly_data = data["monthly_data"]
        assert len(monthly_data) > 0
        assert all("month" in item for item in monthly_data)
        assert all("total" in item for item in monthly_data)

        # Verify ECharts format structure
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert "xAxis" in echarts
        assert "yAxis" in echarts
        assert "series" in echarts
        assert all(s["type"] == "bar" for s in echarts["series"])

    def test_get_monthly_expenses_with_parameters(
        self,
        integration_client: FlaskClient,
        test_project: Project,
        test_expenses: list[Expense],
    ) -> None:
        """Test monthly expenses with query parameters.

        Given: Project with expenses
        When: GET with category and cumulative parameters
        Then: Response reflects filters correctly
        """
        response = integration_client.get(
            f"/v0/projects/{test_project.id}/statistics/expenses/monthly",
            query_string={"category": "labor", "cumulative": "true"},
        )

        assert response.status_code == 200

        data = response.json["data"]  # type: ignore[index]
        assert data["cumulative"] is True

        # When filtering by single category, monthly data should only have month and total
        monthly_data = data["monthly_data"]
        if len(monthly_data) > 0:
            assert "month" in monthly_data[0]
            assert "total" in monthly_data[0]
