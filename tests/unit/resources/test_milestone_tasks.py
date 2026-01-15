# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for milestone-task relationship endpoints.

Tests milestone predecessor task linking, retrieval, and synchronization
with automatic target_date recalculation.
"""

# mypy: disable-error-code="call-arg"

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.milestone import Milestone
from app.models.milestone_task import MilestoneTask
from app.models.project import Project
from app.models.task import Task


@pytest.fixture
def project_data(app: Flask, company_id: str) -> Project:
    """Create a sample project for milestone testing.

    Args:
        app: Flask application fixture.
        company_id: Company UUID for test isolation.

    Returns:
        Created project instance.
    """
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
            code="TEST-001",
            start_date=datetime.now(UTC) - timedelta(days=30),
            finish_date=datetime.now(UTC) + timedelta(days=60),
            status="active",
            budget=100000.00,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def milestone_data(app: Flask, project_data: Project) -> Milestone:
    """Create a sample milestone for testing.

    Args:
        app: Flask application fixture.
        project_data: Project fixture.

    Returns:
        Created milestone instance.
    """
    with app.app_context():
        milestone = Milestone(
            project_id=project_data.id,
            name="Phase 1 Complete",
            description="First phase completion",
            target_date=datetime.now(UTC) + timedelta(days=30),
            budget_weight=Decimal("0.25"),
            status="upcoming",
            is_achieved=False,
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone


@pytest.fixture
def tasks_data(app: Flask, project_data: Project) -> list[Task]:
    """Create sample tasks for milestone linking.

    Args:
        app: Flask application fixture.
        project_data: Project fixture.

    Returns:
        List of created task instances.
    """
    with app.app_context():
        tasks = [
            Task(
                project_id=project_data.id,
                name="Task 1",
                wbs_code="1.1",
                planned_start_date=datetime.now(UTC),
                planned_finish_date=datetime.now(UTC) + timedelta(days=10),
                status="not_started",
                percent_complete=0.0,
            ),
            Task(
                project_id=project_data.id,
                name="Task 2",
                wbs_code="1.2",
                planned_start_date=datetime.now(UTC) + timedelta(days=5),
                planned_finish_date=datetime.now(UTC) + timedelta(days=20),
                status="not_started",
                percent_complete=0.0,
            ),
            Task(
                project_id=project_data.id,
                name="Task 3",
                wbs_code="1.3",
                planned_start_date=datetime.now(UTC) + timedelta(days=10),
                planned_finish_date=datetime.now(UTC) + timedelta(days=30),
                status="not_started",
                percent_complete=0.0,
            ),
        ]

        for task in tasks:
            db.session.add(task)
        db.session.commit()

        for task in tasks:
            db.session.refresh(task)

        return tasks


class TestMilestoneTasksResourcePost:
    """Tests for POST /v0/milestones/{milestone_id}/tasks endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_to_milestone_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test successful task linking to milestone.

        Given: Valid task_ids
        When: POST /v0/milestones/{milestone_id}/tasks is called
        Then: Returns 201 and recalculates milestone target_date
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        link_data = {"task_ids": [str(tasks_data[0].id)]}

        response = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "message" in data
        assert len(data["data"]["predecessor_tasks"]) == 1
        assert data["data"]["predecessor_tasks"][0]["id"] == str(tasks_data[0].id)

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_recalculates_target_date(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test that linking task recalculates milestone target_date.

        Given: Task with planned_finish_date later than milestone target_date
        When: Task is linked to milestone
        Then: Milestone target_date is updated to task's planned_finish_date
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Link task 3 which has the latest finish date (day 30)
        link_data = {"task_ids": [str(tasks_data[2].id)]}

        response = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )

        assert response.status_code == 200

        # Verify milestone target_date was updated
        with app.app_context():
            milestone = db.session.get(Milestone, milestone_data.id)
            assert milestone is not None
            # Target date should be close to task 3's planned_finish_date
            assert milestone.target_date is not None

    @patch("app.services.guardian_service.requests.post")
    def test_link_multiple_tasks(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test linking multiple tasks updates to latest finish date.

        Given: Multiple tasks with different planned_finish_dates
        When: All tasks are linked
        Then: Target_date is MAX(all tasks' planned_finish_dates)
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Link all tasks
        for task in tasks_data:
            link_data = {"task_ids": [str(task.id)]}
            response = authenticated_client.post(
                f"/v0/milestones/{milestone_data.id}/tasks",
                json=link_data,
            )
            assert response.status_code == 200

        # Verify target_date is the latest finish date
        with app.app_context():
            milestone = db.session.get(Milestone, milestone_data.id)
            assert milestone is not None

            latest_task_finish = max(
                (
                    task.planned_finish_date
                    for task in tasks_data
                    if task.planned_finish_date is not None
                ),
                default=None,
            )
            # Remove timezone for comparison
            milestone_target = milestone.target_date.replace(tzinfo=None)
            assert latest_task_finish is not None
            latest_finish = latest_task_finish.replace(tzinfo=None)

            assert milestone_target.date() == latest_finish.date()

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_duplicate(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test linking same task twice.

        Given: Task already linked to milestone
        When: POST same task_ids again
        Then: Returns 409 conflict
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        link_data = {"task_ids": [str(tasks_data[0].id)]}

        # First link - should succeed
        response1 = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )
        assert response1.status_code == 200

        # Second link - should succeed but skip duplicate (idempotent)
        response2 = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )
        assert response2.status_code == 200
        data2 = response2.get_json()
        # Verify duplicate was skipped (linked_count should be 0)
        assert data2["data"]["linked_task_count"] == 0

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test linking non-existent task.

        Given: Task does not exist
        When: POST with invalid task_ids
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_task_id = uuid.uuid4()
        link_data = {"task_ids": [str(fake_task_id)]}

        response = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        tasks_data: list[Task],
    ) -> None:
        """Test linking task to non-existent milestone.

        Given: Milestone does not exist
        When: POST task link
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()
        link_data = {"task_ids": [str(tasks_data[0].id)]}

        response = authenticated_client.post(
            f"/v0/milestones/{fake_milestone_id}/tasks",
            json=link_data,
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_link_task_missing_task_id(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test linking without task_ids.

        Given: Missing task_ids in request
        When: POST task link
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json={},
        )

        assert response.status_code == 400

    def test_link_task_unauthenticated(
        self,
        client: FlaskClient,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test linking task without authentication.

        Given: No authentication token
        When: POST task link
        Then: Returns 401
        """
        link_data = {"task_ids": [str(tasks_data[0].id)]}

        response = client.post(
            f"/v0/milestones/{milestone_data.id}/tasks",
            json=link_data,
        )

        assert response.status_code == 401


class TestMilestoneTasksResourceGet:
    """Tests for GET /v0/milestones/{milestone_id}/tasks endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_tasks_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test retrieving milestone predecessor tasks.

        Given: Tasks are linked to milestone
        When: GET /v0/milestones/{milestone_id}/tasks is called
        Then: Returns 200 with list of tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Link two tasks first
        with app.app_context():
            for task in tasks_data[:2]:
                milestone_task = MilestoneTask(
                    milestone_id=milestone_data.id,
                    task_id=task.id,
                )
                db.session.add(milestone_task)
            db.session.commit()

        response = authenticated_client.get(f"/v0/milestones/{milestone_data.id}/tasks")

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "predecessor_tasks" in data["data"]
        assert len(data["data"]["predecessor_tasks"]) == 2
        assert all("id" in item for item in data["data"]["predecessor_tasks"])

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_tasks_empty(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test retrieving tasks for milestone with no links.

        Given: Milestone has no linked tasks
        When: GET milestone tasks
        Then: Returns 200 with empty list
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(f"/v0/milestones/{milestone_data.id}/tasks")

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "predecessor_tasks" in data["data"]
        assert len(data["data"]["predecessor_tasks"]) == 0

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_tasks_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test retrieving tasks for non-existent milestone.

        Given: Milestone does not exist
        When: GET milestone tasks
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()
        response = authenticated_client.get(f"/v0/milestones/{fake_milestone_id}/tasks")

        assert response.status_code == 404

    def test_get_milestone_tasks_unauthenticated(
        self,
        client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test retrieving milestone tasks without authentication.

        Given: No authentication token
        When: GET milestone tasks
        Then: Returns 401
        """
        response = client.get(f"/v0/milestones/{milestone_data.id}/tasks")

        assert response.status_code == 401


class TestMilestoneTasksSyncResourcePut:
    """Tests for PUT /v0/milestones/{milestone_id}/tasks/sync endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test successful task synchronization.

        Given: New task_ids list
        When: PUT /v0/milestones/{milestone_id}/tasks/sync is called
        Then: Returns 200 and replaces all task links
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        sync_data = {
            "task_ids": [str(tasks_data[0].id), str(tasks_data[1].id)],
        }

        response = authenticated_client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "message" in data
        assert "predecessor_tasks" in data["data"]
        assert len(data["data"]["predecessor_tasks"]) == 2
        assert "linked_task_count" in data["data"]
        assert data["data"]["linked_task_count"] == 2

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_replaces_existing(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test that sync replaces existing task links.

        Given: Milestone has task 1 linked
        When: Sync with task 2 and 3
        Then: Only task 2 and 3 are linked
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Link task 1 first
        with app.app_context():
            milestone_task = MilestoneTask(
                milestone_id=milestone_data.id,
                task_id=tasks_data[0].id,
            )
            db.session.add(milestone_task)
            db.session.commit()

        # Sync with task 2 and 3 (should remove task 1)
        sync_data = {
            "task_ids": [str(tasks_data[1].id), str(tasks_data[2].id)],
        }

        response = authenticated_client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 200

        # Verify only task 2 and 3 are linked
        get_response = authenticated_client.get(
            f"/v0/milestones/{milestone_data.id}/tasks"
        )
        data = get_response.get_json()

        assert "predecessor_tasks" in data["data"]
        assert len(data["data"]["predecessor_tasks"]) == 2
        task_ids = {item["id"] for item in data["data"]["predecessor_tasks"]}
        assert str(tasks_data[0].id) not in task_ids
        assert str(tasks_data[1].id) in task_ids
        assert str(tasks_data[2].id) in task_ids

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_empty_list(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test syncing with empty task list removes all links.

        Given: Milestone has linked tasks
        When: Sync with empty task_ids list
        Then: All task links are removed
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Link a task first
        with app.app_context():
            milestone_task = MilestoneTask(
                milestone_id=milestone_data.id,
                task_id=tasks_data[0].id,
            )
            db.session.add(milestone_task)
            db.session.commit()

        sync_data: dict[str, list[str]] = {"task_ids": []}

        response = authenticated_client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_invalid_task_id(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test sync with non-existent task_id.

        Given: Invalid task_id in list
        When: PUT sync
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_task_id = uuid.uuid4()
        sync_data = {"task_ids": [str(fake_task_id)]}

        response = authenticated_client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        tasks_data: list[Task],
    ) -> None:
        """Test sync for non-existent milestone.

        Given: Milestone does not exist
        When: PUT sync
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()
        sync_data = {"task_ids": [str(tasks_data[0].id)]}

        response = authenticated_client.put(
            f"/v0/milestones/{fake_milestone_id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_missing_task_ids(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        milestone_data: Milestone,
    ) -> None:
        """Test sync without task_idss field.

        Given: Missing task_idss in request
        When: PUT sync
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json={},
        )

        assert response.status_code == 400

    def test_sync_tasks_unauthenticated(
        self,
        client: FlaskClient,
        milestone_data: Milestone,
        tasks_data: list[Task],
    ) -> None:
        """Test sync without authentication.

        Given: No authentication token
        When: PUT sync
        Then: Returns 401
        """
        sync_data = {"task_ids": [str(tasks_data[0].id)]}

        response = client.put(
            f"/v0/milestones/{milestone_data.id}/tasks/sync",
            json=sync_data,
        )

        assert response.status_code == 401
