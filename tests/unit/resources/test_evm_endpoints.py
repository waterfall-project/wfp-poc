# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for EVM endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.milestone_rae import MilestoneRAE
from app.models.project import Project
from app.models.task import Task


@pytest.fixture
def project(app: Flask, company_id: str) -> Project:
    """Create a project for EVM tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="EVM Project",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            finish_date=datetime(2026, 12, 31, tzinfo=UTC),
            budget=Decimal("100000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def evm_data(app: Flask, project: Project) -> None:
    """Create tasks, milestones, expenses, and RAE for EVM calculations."""
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


class TestProjectEVMResource:
    """Tests for GET /v0/projects/{project_id}/evm."""

    @patch("app.services.guardian_service.requests.post")
    def test_evm_indicators_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        evm_data: None,
    ) -> None:
        """Test successful EVM indicators response.

        Given: Project with tasks, expenses, and RAE
        When: GET indicators is called
        Then: Returns computed values
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/evm?as_of_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        data = payload["data"]
        assert data["bac"] == pytest.approx(100000.0)
        assert data["pv"] == pytest.approx(100000.0)
        assert data["ac"] == pytest.approx(40000.0)
        assert data["ev_physical"] == pytest.approx(44444.44, rel=1e-2)
        assert data["ev_milestone"] == pytest.approx(50000.0)


class TestProjectEVMTimeSeriesResource:
    """Tests for GET /v0/projects/{project_id}/evm/timeseries."""

    @patch("app.services.guardian_service.requests.post")
    def test_time_series_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        evm_data: None,
    ) -> None:
        """Test EVM time series response.

        Given: Project with data
        When: GET time series is called
        Then: Returns arrays with matching lengths
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/evm/timeseries"
            "?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        series = payload["data"]["series"]
        assert series
        assert all("date" in point for point in series)


class TestProjectEVMForecastsResource:
    """Tests for GET /v0/projects/{project_id}/evm/forecasts."""

    @patch("app.services.guardian_service.requests.post")
    def test_forecasts_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        evm_data: None,
    ) -> None:
        """Test EVM forecasts response.

        Given: Project with data
        When: GET forecasts is called
        Then: Returns forecast methods
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/evm/forecasts?as_of_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200
        payload = response.get_json()
        forecasts = payload["data"]["forecasts"]
        methods = {item["method"] for item in forecasts}
        assert "cpi" in methods
        assert "cpi_spi" in methods
        assert "plan_based" in methods
