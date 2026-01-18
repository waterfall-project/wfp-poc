"""Unit tests for statistics monthly expenses endpoint.

This module tests the MonthlyExpensesResource endpoint for
retrieving monthly expense distribution.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.expense import Expense
from app.models.project import Project


class TestMonthlyExpensesEndpoint:
    """Tests for GET /projects/{project_id}/statistics/expenses/monthly endpoint."""

    @pytest.fixture
    def project(self, app: Flask, company_id: str) -> Project:
        """Create a test project.

        Args:
            app: Flask application instance.
            company_id: Company ID from JWT fixture.

        Returns:
            Created project instance.
        """
        from app import db

        with app.app_context():
            project = Project(
                id=uuid4(),
                name="Test Project",
                company_id=UUID(company_id),
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
        """Create test expenses across multiple months.

        Args:
            app: Flask application instance.
            project: Test project.

        Returns:
            List of created expense instances.
        """
        from app import db

        with app.app_context():
            expenses = [
                # November 2024
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
                    category="subcontracting",
                    date=datetime(2024, 11, 20, tzinfo=UTC),
                    amount=Decimal("15000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="procurement",
                    date=datetime(2024, 11, 25, tzinfo=UTC),
                    amount=Decimal("6000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="overhead",
                    date=datetime(2024, 11, 28, tzinfo=UTC),
                    amount=Decimal("2000.00"),
                ),
                # December 2024
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="labor",
                    date=datetime(2024, 12, 10, tzinfo=UTC),
                    amount=Decimal("42000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="subcontracting",
                    date=datetime(2024, 12, 15, tzinfo=UTC),
                    amount=Decimal("20000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="procurement",
                    date=datetime(2024, 12, 20, tzinfo=UTC),
                    amount=Decimal("12000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="overhead",
                    date=datetime(2024, 12, 28, tzinfo=UTC),
                    amount=Decimal("3000.00"),
                ),
                # January 2025
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="labor",
                    date=datetime(2025, 1, 10, tzinfo=UTC),
                    amount=Decimal("45000.00"),
                ),
                Expense(
                    id=uuid4(),
                    project_id=project.id,
                    category="subcontracting",
                    date=datetime(2025, 1, 15, tzinfo=UTC),
                    amount=Decimal("25000.00"),
                ),
            ]
            db.session.add_all(expenses)
            db.session.commit()
            for exp in expenses:
                db.session.refresh(exp)
            return expenses

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test retrieving monthly expense distribution.

        Given: Project with expenses across multiple months
        When: GET /projects/{id}/statistics/expenses/monthly is called
        Then: Status is 200 and monthly data is correct
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["project_id"] == str(project.id)
        assert data["cumulative"] is False

        # Verify monthly data
        monthly_data = data["monthly_data"]
        assert len(monthly_data) == 3

        # November 2024
        nov_data = monthly_data[0]
        assert nov_data["month"] == "2024-11"
        assert nov_data["total"] == 48000.0
        assert nov_data["labor"] == 25000.0
        assert nov_data["subcontracting"] == 15000.0
        assert nov_data["procurement"] == 6000.0
        assert nov_data["overhead"] == 2000.0

        # December 2024
        dec_data = monthly_data[1]
        assert dec_data["month"] == "2024-12"
        assert dec_data["total"] == 77000.0
        assert dec_data["labor"] == 42000.0

        # January 2025
        jan_data = monthly_data[2]
        assert jan_data["month"] == "2025-01"
        assert jan_data["total"] == 70000.0

        # Verify ECharts format
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert echarts["xAxis"]["type"] == "category"
        assert echarts["xAxis"]["data"] == ["2024-11", "2024-12", "2025-01"]
        assert echarts["yAxis"]["type"] == "value"

        # Verify stacked series
        series = echarts["series"]
        assert len(series) == 4
        assert series[0]["name"] == "Labor"
        assert series[0]["type"] == "bar"
        assert series[0]["stack"] == "total"
        assert series[0]["data"] == [25000.0, 42000.0, 45000.0]

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_cumulative(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test monthly expenses with cumulative values.

        Given: Expenses across multiple months
        When: GET with cumulative=true is called
        Then: Values are cumulative
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly",
            query_string={"cumulative": "true"},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["cumulative"] is True

        monthly_data = data["monthly_data"]

        # November: 48000
        assert monthly_data[0]["total"] == 48000.0
        assert monthly_data[0]["labor"] == 25000.0

        # December: cumulative 48000 + 77000 = 125000
        assert monthly_data[1]["total"] == 125000.0
        assert monthly_data[1]["labor"] == 67000.0  # 25000 + 42000

        # January: cumulative 125000 + 70000 = 195000
        assert monthly_data[2]["total"] == 195000.0
        assert monthly_data[2]["labor"] == 112000.0  # 67000 + 45000

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_with_category_filter(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test monthly expenses filtered by category.

        Given: Expenses in multiple categories
        When: GET with category=labor is called
        Then: Only labor expenses are included
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly",
            query_string={"category": "labor"},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        monthly_data = data["monthly_data"]

        # November labor only
        assert monthly_data[0]["total"] == 25000.0
        # No category breakdown for single category filter
        assert "labor" not in monthly_data[0]

        # December labor only
        assert monthly_data[1]["total"] == 42000.0

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_with_date_range(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        expenses: list[Expense],
    ) -> None:
        """Test monthly expenses with date range.

        Given: Expenses across multiple months
        When: GET with start_date is called
        Then: Only expenses after start_date are included
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly",
            query_string={"start_date": "2024-12-01T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        monthly_data = data["monthly_data"]
        # Only December and January
        assert len(monthly_data) == 2
        assert monthly_data[0]["month"] == "2024-12"
        assert monthly_data[1]["month"] == "2025-01"

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_invalid_category(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
    ) -> None:
        """Test monthly expenses with invalid category.

        Given: Valid project
        When: GET with invalid category is called
        Then: Status is 400
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly",
            query_string={"category": "invalid"},
        )

        assert response.status_code == 400

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_project_not_found(
        self, mock_guardian: MagicMock, authenticated_client: FlaskClient
    ) -> None:
        """Test monthly expenses for non-existent project.

        Given: Invalid project ID
        When: GET is called
        Then: Status is 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_id = uuid4()
        response = authenticated_client.get(
            f"/v0/projects/{fake_id}/statistics/expenses/monthly"
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_get_monthly_expenses_no_expenses(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
    ) -> None:
        """Test monthly expenses with no expenses.

        Given: Project with no expenses
        When: GET is called
        Then: Status is 200 with empty monthly_data
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/expenses/monthly"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["monthly_data"] == []
