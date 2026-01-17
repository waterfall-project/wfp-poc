# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Expense resources."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from app.models.db import db
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.project import Project
from app.models.resource import Resource

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


def _create_project(company_id: str) -> Project:
    start_date = datetime(2024, 1, 1, 9, 0)
    finish_date = start_date + timedelta(days=30)
    project = Project(
        company_id=uuid.UUID(company_id),
        name="Test Project",
        code="TP-001",
        start_date=start_date,
        finish_date=finish_date,
        status="active",
    )
    db.session.add(project)
    db.session.commit()
    db.session.refresh(project)
    return project


def _create_milestone(project: Project, name: str, target_date: datetime) -> Milestone:
    milestone = Milestone(
        project_id=project.id,
        name=name,
        target_date=target_date,
        budget_weight=Decimal("0.5"),
        status="upcoming",
        is_achieved=False,
    )
    db.session.add(milestone)
    db.session.commit()
    db.session.refresh(milestone)
    return milestone


def _create_resource(company_id: str) -> Resource:
    resource = Resource(
        company_id=uuid.UUID(company_id),
        name="Test Resource",
        type="labor",
        email="resource@example.com",
    )
    db.session.add(resource)
    db.session.commit()
    db.session.refresh(resource)
    return resource


def _create_expense(
    project: Project,
    milestone: Milestone,
    date: datetime,
    amount: Decimal,
    reference_number: str | None = None,
    resource: Resource | None = None,
) -> Expense:
    expense = Expense(
        project_id=project.id,
        date=date,
        amount=amount,
        category="procurement",
        description="Seed expense",
        milestone_id=milestone.id,
        resource_id=resource.id if resource else None,
        reference_number=reference_number,
    )
    db.session.add(expense)
    db.session.commit()
    db.session.refresh(expense)
    return expense


class TestExpenseCreate:
    """Tests for POST /v0/projects/{project_id}/expenses."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_expense_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test creating expense assigns milestone.

        Given: Valid expense payload within milestone date range
        When: POST /expenses is called
        Then: Returns 201 and assigns milestone_id
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            milestone_early = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            _create_milestone(project, "Phase 2", datetime(2026, 3, 20, 0, 0))

        payload = {
            "date": "2026-02-20T00:00:00Z",
            "amount": 1500.00,
            "category": "procurement",
            "description": "Procurement expense",
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/expenses", json=payload
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["data"]["milestone_id"] == str(milestone_early.id)
        assert body["data"]["amount"] == 1500.0

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_expense_duplicate_returns_conflict(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test duplicate expense detection.

        Given: Existing expense with same reference_number/date/amount
        When: POST /expenses is called with duplicate payload
        Then: Returns 409 conflict
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            expense_date = datetime(2026, 2, 20, 0, 0, tzinfo=UTC)
            _create_expense(
                project,
                milestone,
                expense_date,
                Decimal("1000.00"),
                reference_number="REF-001",
            )

        payload = {
            "date": "2026-02-20T00:00:00Z",
            "amount": 1000.00,
            "category": "procurement",
            "reference_number": "REF-001",
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/expenses", json=payload
        )

        assert response.status_code == 409

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_expense_outside_milestone_range_returns_unprocessable(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test expense date outside milestone range.

        Given: Expense date before first milestone target_date
        When: POST /expenses is called
        Then: Returns 422 validation error
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            _create_milestone(project, "Phase 1", datetime(2026, 2, 20, 0, 0))

        payload = {
            "date": "2026-02-01T10:00:00Z",
            "amount": 1000.00,
            "category": "procurement",
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/expenses", json=payload
        )

        assert response.status_code == 422


class TestExpenseList:
    """Tests for GET /v0/projects/{project_id}/expenses."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_list_expenses_with_filters(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test listing expenses with filters.

        Given: Expenses exist for project
        When: GET /expenses with category filter
        Then: Returns paginated list
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            _create_expense(
                project,
                milestone,
                datetime(2026, 2, 20, 0, 0, tzinfo=UTC),
                Decimal("100.00"),
            )

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/expenses?category=procurement"
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["page"] == 1
        assert body["per_page"] == 20
        assert body["total"] == 1


class TestExpenseGet:
    """Tests for GET /v0/projects/{project_id}/expenses/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_get_expense_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test getting missing expense.

        Given: Unknown expense id
        When: GET /expenses/{id} is called
        Then: Returns 404
        """
        mock_guardian.return_value = (True, "granted")

        response = authenticated_client.get(
            "/v0/projects/00000000-0000-0000-0000-000000000000/expenses/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404


class TestExpensePatch:
    """Tests for PATCH /v0/projects/{project_id}/expenses/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_update_expense_reassigns_milestone(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test updating expense date reassigns milestone.

        Given: Expense exists in first milestone range
        When: PATCH /expenses updates date into second range
        Then: milestone_id is updated
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            milestone_early = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            milestone_late = _create_milestone(
                project, "Phase 2", datetime(2026, 3, 20, 0, 0)
            )
            expense = _create_expense(
                project,
                milestone_early,
                datetime(2026, 2, 20, 0, 0, tzinfo=UTC),
                Decimal("200.00"),
            )

        payload = {"date": "2026-03-10T10:00:00Z"}

        response = authenticated_client.patch(
            f"/v0/projects/{project.id}/expenses/{expense.id}", json=payload
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["data"]["milestone_id"] == str(milestone_late.id)


class TestExpenseDelete:
    """Tests for DELETE /v0/projects/{project_id}/expenses/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_delete_expense_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test deleting an expense.

        Given: Existing expense
        When: DELETE /expenses/{id} is called
        Then: Returns 204
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            expense = _create_expense(
                project,
                milestone,
                datetime(2026, 2, 20, 0, 0, tzinfo=UTC),
                Decimal("200.00"),
            )

        response = authenticated_client.delete(
            f"/v0/projects/{project.id}/expenses/{expense.id}"
        )

        assert response.status_code == 204


class TestExpenseBulkCreate:
    """Tests for POST /v0/projects/{project_id}/expenses/bulk."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_bulk_create_expenses_partial_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test bulk create with partial errors.

        Given: One valid and one invalid expense
        When: POST /expenses/bulk is called
        Then: Returns created_count and failed_count
        """
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            _create_milestone(project, "Phase 1", datetime(2026, 2, 20, 0, 0))
            _create_milestone(project, "Phase 2", datetime(2026, 3, 20, 0, 0))

        payload = {
            "expenses": [
                {
                    "date": "2026-02-20T00:00:00Z",
                    "amount": 100.00,
                    "category": "procurement",
                },
                {
                    "date": "2026-01-01T10:00:00Z",
                    "amount": 200.00,
                    "category": "procurement",
                },
            ]
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/expenses/bulk", json=payload
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["data"]["created_count"] == 1
        assert body["data"]["failed_count"] == 1
        assert len(body["data"]["errors"]) == 1
