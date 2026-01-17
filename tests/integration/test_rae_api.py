# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for RAE endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.db import db
from app.models.milestone import Milestone
from app.models.project import Project


@pytest.fixture
def project(app, company_id):
    """Create a project for RAE integration tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="RAE Integration Project",
            start_date=datetime.now(UTC) - timedelta(days=30),
            finish_date=datetime.now(UTC) + timedelta(days=180),
            budget=Decimal("200000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def milestone(app, project):
    """Create a milestone for RAE integration tests."""
    with app.app_context():
        milestone = Milestone(
            project_id=project.id,
            name="Phase 1",
            target_date=datetime(2026, 6, 30, tzinfo=UTC),
            budget_weight=Decimal("0.5"),
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone


class TestMilestoneRAEAPI:
    """Integration tests for milestone RAE endpoints."""

    def test_create_and_history(self, integration_client, milestone):
        """Test RAE creation and history retrieval.

        Given: A milestone
        When: POST RAE and GET history
        Then: Responses are successful and consistent
        """
        payload = {
            "date": "2026-06-30T23:59:59Z",
            "amount": 15000.00,
            "comment": "Backend delay",
        }

        create_response = integration_client.post(
            f"/v0/milestones/{milestone.id}/rae", json=payload
        )
        assert create_response.status_code == 201

        history_response = integration_client.get(
            f"/v0/milestones/{milestone.id}/rae/history"
        )
        assert history_response.status_code == 200
        history_payload = history_response.get_json()
        assert history_payload["total"] == 1
        assert history_payload["data"][0]["amount"] == pytest.approx(15000.0)


class TestProjectRAESummaryAPI:
    """Integration tests for project RAE summary."""

    def test_summary(self, integration_client, project, milestone):
        """Test summary endpoint returns totals.

        Given: RAE entry for milestone
        When: GET summary
        Then: Returns total RAE
        """
        payload = {
            "date": "2026-06-30T23:59:59Z",
            "amount": 12000.00,
        }
        integration_client.post(f"/v0/milestones/{milestone.id}/rae", json=payload)

        response = integration_client.get(f"/v0/projects/{project.id}/rae/summary")
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["total_rae"] == pytest.approx(12000.0)
        assert len(data["milestones"]) == 1
