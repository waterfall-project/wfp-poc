# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for RAE endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.milestone import Milestone
from app.models.project import Project


@pytest.fixture
def project(app: Flask, company_id: str) -> Project:
    """Create a project for RAE tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="RAE Project",
            start_date=datetime.now(UTC) - timedelta(days=30),
            finish_date=datetime.now(UTC) + timedelta(days=180),
            budget=Decimal("250000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def milestone(app: Flask, project: Project) -> Milestone:
    """Create a milestone for RAE tests."""
    with app.app_context():
        milestone = Milestone(
            project_id=project.id,
            name="Design Complete",
            target_date=datetime.now(UTC) + timedelta(days=30),
            budget_weight=Decimal("0.5"),
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone


class TestMilestoneRAEResource:
    """Tests for POST /v0/milestones/{milestone_id}/rae."""

    @patch("app.services.guardian_service.requests.post")
    def test_create_rae_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone: Milestone,
    ) -> None:
        """Test successful RAE creation.

        Given: Valid RAE payload
        When: POST is called
        Then: Returns 201 and persists RAE
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "date": "2026-06-30T23:59:59Z",
            "amount": 15000.00,
            "comment": "Backend delay",
            "details": {
                "task_estimates": [
                    {
                        "task_id": str(uuid.uuid4()),
                        "task_name": "Backend",
                        "remaining_cost": 8000.00,
                        "comment": "Migration risk",
                    }
                ]
            },
        }

        response = authenticated_client.post(
            f"/v0/milestones/{milestone.id}/rae",
            json=payload,
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["data"]["milestone_id"] == str(milestone.id)
        assert data["data"]["amount"] == pytest.approx(15000.0)
        assert data["message"] == "RAE updated successfully"

        with app.app_context():
            refreshed = db.session.get(Milestone, milestone.id)
            assert refreshed is not None
            assert refreshed.current_rae == Decimal("15000.00")

    @patch("app.services.guardian_service.requests.post")
    def test_create_rae_negative_amount(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone: Milestone,
    ) -> None:
        """Test RAE validation for negative amount.

        Given: Negative amount
        When: POST is called
        Then: Returns 400
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "date": "2026-06-30T23:59:59Z",
            "amount": -1,
        }

        response = authenticated_client.post(
            f"/v0/milestones/{milestone.id}/rae",
            json=payload,
        )

        assert response.status_code == 400


class TestMilestoneRAEHistoryResource:
    """Tests for GET /v0/milestones/{milestone_id}/rae/history."""

    @patch("app.services.guardian_service.requests.post")
    def test_history_returns_ordered_entries(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone: Milestone,
    ) -> None:
        """Test history response ordering.

        Given: Multiple RAE entries
        When: GET history is called
        Then: Returns entries ordered by date asc
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            from app.models.milestone_rae import MilestoneRAE

            rae1 = MilestoneRAE(
                milestone_id=milestone.id,
                date=datetime(2026, 5, 31, 23, 59, 59, tzinfo=UTC),
                amount=Decimal("12000.00"),
                updated_by=uuid.uuid4(),
            )
            rae2 = MilestoneRAE(
                milestone_id=milestone.id,
                date=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
                amount=Decimal("15000.00"),
                updated_by=uuid.uuid4(),
            )
            db.session.add_all([rae2, rae1])
            db.session.commit()

        response = authenticated_client.get(
            f"/v0/milestones/{milestone.id}/rae/history"
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["total"] == 2
        assert payload["data"][0]["amount"] == pytest.approx(12000.0)
        assert payload["data"][1]["amount"] == pytest.approx(15000.0)


class TestProjectRAESummaryResource:
    """Tests for GET /v0/projects/{project_id}/rae/summary."""

    @patch("app.services.guardian_service.requests.post")
    def test_summary_returns_total(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        project: Project,
    ) -> None:
        """Test project RAE summary.

        Given: Project milestones with RAE entries
        When: GET summary is called
        Then: Returns total and milestone breakdown
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            milestone_a = Milestone(
                project_id=project.id,
                name="Phase 1",
                target_date=datetime(2026, 5, 31, tzinfo=UTC),
                budget_weight=Decimal("0.4"),
            )
            milestone_b = Milestone(
                project_id=project.id,
                name="Phase 2",
                target_date=datetime(2026, 6, 30, tzinfo=UTC),
                budget_weight=Decimal("0.6"),
            )
            db.session.add_all([milestone_a, milestone_b])
            db.session.commit()

            from app.models.milestone_rae import MilestoneRAE

            rae_a = MilestoneRAE(
                milestone_id=milestone_a.id,
                date=datetime(2026, 5, 31, 23, 59, 59, tzinfo=UTC),
                amount=Decimal("10000.00"),
                updated_by=uuid.uuid4(),
            )
            rae_b = MilestoneRAE(
                milestone_id=milestone_b.id,
                date=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
                amount=Decimal("15000.00"),
                updated_by=uuid.uuid4(),
            )
            db.session.add_all([rae_a, rae_b])
            db.session.commit()

        response = authenticated_client.get(f"/v0/projects/{project.id}/rae/summary")

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["data"]["total_rae"] == pytest.approx(25000.0)
        assert len(payload["data"]["milestones"]) == 2
