# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for Expense API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from app.models.db import db
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.project import Project

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


def _create_project(company_id: str) -> Project:
    start_date = datetime(2024, 1, 1, 9, 0)
    finish_date = start_date + timedelta(days=30)
    project = Project(
        company_id=uuid.UUID(company_id),
        name="Integration Project",
        code="INT-EXP-001",
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


def _create_expense(
    project: Project,
    milestone: Milestone,
    date: datetime,
    amount: Decimal,
    reference_number: str | None = None,
) -> Expense:
    expense = Expense(
        project_id=project.id,
        date=date,
        amount=amount,
        category="procurement",
        description="Seed expense",
        milestone_id=milestone.id,
        reference_number=reference_number,
    )
    db.session.add(expense)
    db.session.commit()
    db.session.refresh(expense)
    return expense


class TestExpensesApi:
    """Integration tests for expense endpoints."""

    def test_create_expense_success(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test creating expense successfully.

        Given: Valid payload within milestone range
        When: POST /expenses is called
        Then: Returns 201 with allocated milestone_id
        """
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            _create_milestone(project, "Phase 2", datetime(2026, 3, 20, 0, 0))

        payload = {
            "date": "2026-02-20T00:00:00Z",
            "amount": 1200.00,
            "category": "procurement",
            "description": "Procurement expense",
        }

        response = integration_client.post(
            f"/v0/projects/{project.id}/expenses", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["data"]["milestone_id"] == str(milestone.id)

    def test_list_expenses_filters(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test listing expenses with filters.

        Given: Expenses exist
        When: GET /expenses with category filter
        Then: Returns filtered results
        """
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

        response = integration_client.get(
            f"/v0/projects/{project.id}/expenses?category=procurement"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1

    def test_get_expense_success(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test retrieving a single expense.

        Given: An existing expense
        When: GET /expenses/{id} is called
        Then: Returns 200 with expense data
        """
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            expense = _create_expense(
                project,
                milestone,
                datetime(2026, 2, 20, 0, 0, tzinfo=UTC),
                Decimal("100.00"),
            )

        response = integration_client.get(
            f"/v0/projects/{project.id}/expenses/{expense.id}"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["id"] == str(expense.id)

    def test_patch_expense_updates_milestone(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test updating expense date reassigns milestone.

        Given: Expense in early milestone
        When: PATCH /expenses updates date into later range
        Then: milestone_id is updated
        """
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
                Decimal("100.00"),
            )

        response = integration_client.patch(
            f"/v0/projects/{project.id}/expenses/{expense.id}",
            json={"date": "2026-03-10T10:00:00Z"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["milestone_id"] == str(milestone_late.id)

    def test_delete_expense_success(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test deleting an expense.

        Given: Existing expense
        When: DELETE /expenses/{id} is called
        Then: Returns 204 and deletes expense
        """
        with app.app_context():
            project = _create_project(company_id)
            milestone = _create_milestone(
                project, "Phase 1", datetime(2026, 2, 20, 0, 0)
            )
            expense = _create_expense(
                project,
                milestone,
                datetime(2026, 2, 20, 0, 0, tzinfo=UTC),
                Decimal("100.00"),
            )

        response = integration_client.delete(
            f"/v0/projects/{project.id}/expenses/{expense.id}"
        )

        assert response.status_code == 204

    def test_bulk_create_expenses_partial_success(
        self, app: Flask, integration_client: FlaskClient, company_id: str
    ) -> None:
        """Test bulk expense creation with partial errors.

        Given: One valid and one invalid expense
        When: POST /expenses/bulk is called
        Then: Returns 201 with created/failed counts
        """
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

        response = integration_client.post(
            f"/v0/projects/{project.id}/expenses/bulk", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["data"]["created_count"] == 1
        assert data["data"]["failed_count"] == 1
