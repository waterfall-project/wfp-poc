# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for EVM endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.db import db
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.milestone_rae import MilestoneRAE
from app.models.project import Project
from app.models.task import Task


@pytest.fixture
def project(app, company_id):
    """Create a project for EVM integration tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="EVM Integration Project",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            finish_date=datetime(2026, 12, 31, tzinfo=UTC),
            budget=Decimal("100000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def evm_seed(app, project):
    """Seed tasks, milestones, expenses, and RAE for EVM endpoints."""
    with app.app_context():
        task = Task(
            project_id=project.id,
            name="Planned Task",
            planned_start_date=datetime(2026, 1, 1, tzinfo=UTC),
            planned_finish_date=datetime(2026, 1, 31, tzinfo=UTC),
            planned_cost=Decimal("100000.00"),
        )
        milestone = Milestone(
            project_id=project.id,
            name="Phase 1",
            target_date=datetime(2026, 1, 31, tzinfo=UTC),
            budget_weight=Decimal("0.5"),
            is_achieved=True,
            achieved_date=datetime(2026, 1, 31, tzinfo=UTC),
        )
        expense = Expense(
            project_id=project.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("40000.00"),
            category="labor",
        )
        db.session.add_all([task, milestone, expense])
        db.session.commit()

        rae_entry = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("50000.00"),
            updated_by=uuid.uuid4(),
        )
        db.session.add(rae_entry)
        db.session.commit()


class TestEVMIndicatorsAPI:
    """Integration tests for EVM indicators endpoint."""

    def test_get_indicators(self, integration_client, project, evm_seed):
        """Test GET /v0/projects/{project_id}/evm.

        Given: Project with EVM data
        When: GET indicators
        Then: Returns EVM values
        """
        response = integration_client.get(
            f"/v0/projects/{project.id}/evm?as_of_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        data = payload["data"]
        assert data["bac"] == pytest.approx(100000.0)
        assert data["ac"] == pytest.approx(40000.0)


class TestEVMTimeSeriesAPI:
    """Integration tests for EVM time series endpoint."""

    def test_get_time_series(self, integration_client, project, evm_seed):
        """Test GET /v0/projects/{project_id}/evm/timeseries.

        Given: Project with EVM data
        When: GET time series
        Then: Returns arrays of values
        """
        response = integration_client.get(
            f"/v0/projects/{project.id}/evm/timeseries"
            "?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["data"]["series"]


class TestEVMForecastsAPI:
    """Integration tests for EVM forecasts endpoint."""

    def test_get_forecasts(self, integration_client, project, evm_seed):
        """Test GET /v0/projects/{project_id}/evm/forecasts.

        Given: Project with EVM data
        When: GET forecasts
        Then: Returns forecast methods
        """
        response = integration_client.get(
            f"/v0/projects/{project.id}/evm/forecasts?as_of_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        forecasts = payload["data"]["forecasts"]
        methods = {item["method"] for item in forecasts}
        assert "cpi" in methods
