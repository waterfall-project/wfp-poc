# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for milestone endpoints.

Covers CRUD operations on /v0/projects/{project_id}/milestones and
milestone-task linking endpoints with real database interactions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.models.db import db
from app.models.milestone import Milestone
from app.models.project import Project
from app.models.task import Task


def _make_milestone(**kwargs: Any) -> Milestone:
    """Create a Milestone and assign attributes without relying on __init__ kwargs."""

    milestone = Milestone()
    for key, value in kwargs.items():
        setattr(milestone, key, value)
    return milestone


def _make_task(**kwargs: Any) -> Task:
    """Create a Task and assign attributes without relying on __init__ kwargs."""

    task = Task()
    for key, value in kwargs.items():
        setattr(task, key, value)
    return task


@pytest.fixture
def project(app, company_id):
    """Create a project for milestone tests."""

    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Milestone Integration Project",
            code=f"MS-{uuid.uuid4().hex[:8]}",
            start_date=datetime.now(UTC) - timedelta(days=5),
            finish_date=datetime.now(UTC) + timedelta(days=180),
            status="active",
            budget=250_000.00,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def milestone(app, project):
    """Persist a milestone for retrieval/update tests."""

    with app.app_context():
        milestone = _make_milestone(
            project_id=project.id,
            name="Design Review",
            description="Complete design phase review",
            target_date=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
            budget_weight=Decimal("0.35"),
            status="upcoming",
            is_achieved=False,
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone


class TestMilestoneCreate:
    """Integration tests for POST /v0/projects/{project_id}/milestones."""

    def test_create_milestone_success(self, integration_client, app, project):
        """Test successful milestone creation.

        Given: Valid milestone payload within budget constraints
        When: POST /v0/projects/{project_id}/milestones is called
        Then: Response is 201 and milestone persists with provided fields
        """

        payload = {
            "name": "Requirements Qualification",
            "description": "Formal requirements review",
            "target_date": "2026-05-15T18:00:00Z",
            "budget_weight": 0.25,
        }

        response = integration_client.post(
            f"/v0/projects/{project.id}/milestones", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "Milestone created successfully"
        assert data["data"]["name"] == "Requirements Qualification"
        assert float(data["data"]["budget_weight"]) == 0.25

        with app.app_context():
            created = Milestone.query.filter_by(project_id=project.id).first()
            assert created is not None
            assert created.name == "Requirements Qualification"

    def test_create_milestone_budget_conflict(self, integration_client, project, app):
        """Test budget_weight sum enforcement returns 409.

        Given: Existing milestones consume most of the budget_weight
        When: POST /v0/projects/{project_id}/milestones exceeds total budget_weight
        Then: Response is 409 with budget_weight conflict message
        """

        with app.app_context():
            existing = _make_milestone(
                project_id=project.id,
                name="Existing Budget",
                target_date=datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
                budget_weight=Decimal("0.9"),
                status="upcoming",
                is_achieved=False,
            )
            db.session.add(existing)
            db.session.commit()

        response = integration_client.post(
            f"/v0/projects/{project.id}/milestones",
            json={
                "name": "Excess Weight",
                "target_date": "2026-04-10T18:00:00Z",
                "budget_weight": 0.2,
            },
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "budget_weight" in data["message"]


class TestMilestoneRetrieve:
    """Integration tests for GET /v0/projects/{project_id}/milestones/{id}."""

    def test_get_milestone_success(self, integration_client, milestone):
        """Test retrieving a milestone returns 200.

        Given: Milestone exists for the project
        When: GET /v0/projects/{project_id}/milestones/{id} is called
        Then: Response is 200 with correct milestone data
        """

        response = integration_client.get(
            f"/v0/projects/{milestone.project_id}/milestones/{milestone.id}"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["id"] == str(milestone.id)
        assert data["data"]["name"] == "Design Review"
        assert float(data["data"]["budget_weight"]) == 0.35

    def test_get_milestone_not_found(self, integration_client, project):
        """Test missing milestone returns 404.

        Given: No milestone exists for the provided ID
        When: GET /v0/projects/{project_id}/milestones/{id} is called
        Then: Response is 404 with not found message
        """

        response = integration_client.get(
            f"/v0/projects/{project.id}/milestones/{uuid.uuid4()}"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Milestone not found"


class TestMilestoneUpdate:
    """Integration tests for PATCH /v0/projects/{project_id}/milestones/{id}."""

    def test_update_milestone_mark_achieved(self, integration_client, app, milestone):
        """Test marking milestone achieved updates status and dates.

        Given: Existing milestone marked as upcoming
        When: PATCH /v0/projects/{project_id}/milestones/{id} sets is_achieved true
        Then: Response is 200 and milestone status flips to achieved with dates set
        """

        payload = {
            "is_achieved": True,
            "achieved_date": "2026-06-02T12:00:00Z",
            "actual_date": "2026-06-02T12:00:00Z",
        }

        response = integration_client.patch(
            f"/v0/projects/{milestone.project_id}/milestones/{milestone.id}",
            json=payload,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Milestone updated successfully"
        assert data["data"]["is_achieved"] is True
        assert data["data"]["status"] == "achieved"

        with app.app_context():
            refreshed = db.session.get(Milestone, milestone.id)
            assert refreshed is not None
            assert refreshed.is_achieved is True
            assert refreshed.status == "achieved"


class TestMilestoneDelete:
    """Integration tests for DELETE /v0/projects/{project_id}/milestones/{id}."""

    def test_delete_milestone_success(self, integration_client, app, project):
        """Test milestone deletion returns 204 and removes record.

        Given: Milestone exists for the project
        When: DELETE /v0/projects/{project_id}/milestones/{id} is called
        Then: Response is 204 and milestone is removed from database
        """

        with app.app_context():
            deletable = _make_milestone(
                project_id=project.id,
                name="Delete Milestone",
                target_date=datetime(2026, 7, 1, 18, 0, tzinfo=UTC),
                budget_weight=Decimal("0.1"),
                status="upcoming",
                is_achieved=False,
            )
            db.session.add(deletable)
            db.session.commit()
            db.session.refresh(deletable)

        response = integration_client.delete(
            f"/v0/projects/{project.id}/milestones/{deletable.id}"
        )

        assert response.status_code == 204

        with app.app_context():
            removed = db.session.get(Milestone, deletable.id)
            assert removed is None


class TestMilestoneTasksLinking:
    """Integration tests for milestone-task link endpoints."""

    def test_link_tasks_updates_target_date(
        self, integration_client, app, project
    ) -> None:
        """Test task linking recalculates milestone target_date.

        Given: Milestone and tasks with different finish dates exist
        When: POST /v0/milestones/{id}/tasks links both tasks
        Then: Response is 200 and milestone target_date becomes max planned_finish_date
        """

        with app.app_context():
            milestone = _make_milestone(
                project_id=project.id,
                name="Link Target",
                target_date=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
                budget_weight=Decimal("0.2"),
                status="upcoming",
                is_achieved=False,
            )
            task_soon = _make_task(
                project_id=project.id,
                name="Soon Task",
                type="task",
                status="not_started",
                wbs_code="2.1",
                planned_start_date=datetime(2026, 5, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 5, 10, 18, 0, tzinfo=UTC),
                percent_complete=0.0,
            )
            task_late = _make_task(
                project_id=project.id,
                name="Late Task",
                type="task",
                status="not_started",
                wbs_code="2.2",
                planned_start_date=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 6, 20, 18, 0, tzinfo=UTC),
                percent_complete=0.0,
            )
            db.session.add_all([milestone, task_soon, task_late])
            db.session.commit()
            db.session.refresh(milestone)
            db.session.refresh(task_soon)
            db.session.refresh(task_late)

            milestone_id = milestone.id
            late_finish = task_late.planned_finish_date
            task_ids = [str(task_soon.id), str(task_late.id)]

        response = integration_client.post(
            f"/v0/milestones/{milestone_id}/tasks",
            json={"task_ids": task_ids},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert (
            data["message"]
            == "Tasks linked successfully, milestone target_date recalculated"
        )
        assert data["data"]["linked_task_count"] == 2
        assert any(t["name"] == "Late Task" for t in data["data"]["predecessor_tasks"])

        with app.app_context():
            refreshed_milestone = db.session.get(Milestone, milestone_id)
            assert refreshed_milestone is not None
            # Target date should be max of linked task planned_finish_date values
            assert refreshed_milestone.target_date == late_finish


class TestMilestoneList:
    """Integration tests for GET /v0/projects/{project_id}/milestones list."""

    def test_list_milestones_with_status_filter(
        self, integration_client, app, project
    ) -> None:
        """Test listing with status filter and pagination defaults.

        Given: Multiple milestones with distinct statuses exist
        When: GET /v0/projects/{project_id}/milestones is filtered by status
        Then: Response is 200 with only matching milestones and pagination fields
        """

        with app.app_context():
            milestones = [
                _make_milestone(
                    project_id=project.id,
                    name="Upcoming Milestone",
                    target_date=datetime(2026, 9, 1, 18, 0, tzinfo=UTC),
                    budget_weight=Decimal("0.2"),
                    status="upcoming",
                    is_achieved=False,
                ),
                _make_milestone(
                    project_id=project.id,
                    name="Achieved Milestone",
                    target_date=datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
                    actual_date=datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
                    achieved_date=datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
                    budget_weight=Decimal("0.3"),
                    status="achieved",
                    is_achieved=True,
                ),
            ]
            db.session.add_all(milestones)
            db.session.commit()

        response = integration_client.get(
            f"/v0/projects/{project.id}/milestones?status=achieved"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "achieved"
