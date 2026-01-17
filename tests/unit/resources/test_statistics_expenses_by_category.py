"""Unit tests for statistics expense by category endpoint.

This module tests the ExpenseByCategoryResource endpoint for
retrieving expense breakdowns by category.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.expense import Expense
from app.models.project import Project


class TestExpenseByCategoryEndpoint:
    """Tests for GET /projects/{project_id}/statistics/expenses/by-category endpoint."""

    @pytest.fixture
    def project(self, app: Flask) -> Project:
        """Create a test project.

        Args:
            app: Flask application instance.

        Returns:
            Created project instance.
        """
        from app import db

        with app.app_context():
            project = Project(
                id=uuid4(),
                name="Test Project",
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
    def expenses(self, app: Flask, project: Project) -> list[Expense]:
        """Create test expenses.

        Args:
            app: Flask application instance.
            project: Test project.

        Returns:
            List of created expense instances.
        """
        from app import db

        with app.app_context():
            expenses = [
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="labor",
                    date=datetime(2024, 11, 15, tzinfo=UTC),
                    amount=Decimal("25000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="labor",
                    date=datetime(2024, 11, 20, tzinfo=UTC),
                    amount=Decimal("20000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="subcontracting",
                    date=datetime(2024, 12, 1, tzinfo=UTC),
                    amount=Decimal("15000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="procurement",
                    date=datetime(2024, 12, 10, tzinfo=UTC),
                    amount=Decimal("6000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="overhead",
                    date=datetime(2024, 12, 15, tzinfo=UTC),
                    amount=Decimal("2000.00"),
                ),
            ]
            db.session.add_all(expenses)
            db.session.commit()
            for exp in expenses:
                db.session.refresh(exp)
            return expenses

    def test_get_expense_breakdown_success(
        self,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test retrieving expense breakdown by category.

        Given: Project with expenses in multiple categories
        When: GET /projects/{id}/statistics/expenses/by-category is called
        Then: Status is 200 and breakdown is correct
        """
        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/by-category"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["project_id"] == str(project.id)
        assert data["total_expenses"] == 68000.0

        # Verify breakdown
        breakdown = data["breakdown"]
        assert len(breakdown) == 4

        # Check labor (should be first - largest amount)
        labor = next(b for b in breakdown if b["category"] == "labor")
        assert labor["amount"] == 45000.0
        assert labor["percentage"] == pytest.approx(66.18, abs=0.01)
        assert labor["count"] == 2

        # Check subcontracting
        subcontracting = next(b for b in breakdown if b["category"] == "subcontracting")
        assert subcontracting["amount"] == 15000.0
        assert subcontracting["percentage"] == pytest.approx(22.06, abs=0.01)

        # Verify ECharts format
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert len(echarts["series"]) == 1
        assert echarts["series"][0]["name"] == "Expenses by Category"
        assert echarts["series"][0]["type"] == "pie"
        assert len(echarts["series"][0]["data"]) == 4

    def test_get_expense_breakdown_with_date_filter(
        self,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test expense breakdown with date filters.

        Given: Expenses in multiple months
        When: GET with start_date filter is called
        Then: Only expenses after start_date are included
        """
        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/by-category",
            query_string={"start_date": "2024-12-01T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        # Only December expenses
        assert data["total_expenses"] == 23000.0
        assert len(data["breakdown"]) == 3  # subcontracting, procurement, overhead

    def test_get_expense_breakdown_project_not_found(
        self, authenticated_client: FlaskClient
    ) -> None:
        """Test expense breakdown for non-existent project.

        Given: Invalid project ID
        When: GET is called
        Then: Status is 404
        """
        fake_id = uuid4()
        response = authenticated_client.get(
            f"/v0/projects/{fake_id}/statistics/expenses/by-category"
        )

        assert response.status_code == 404

    def test_get_expense_breakdown_no_expenses(
        self, authenticated_client: FlaskClient, project: Project
    ) -> None:
        """Test expense breakdown with no expenses.

        Given: Project with no expenses
        When: GET is called
        Then: Status is 200 with empty breakdown
        """
        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/by-category"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["total_expenses"] == 0.0
        assert data["breakdown"] == []
