# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Task bulk and sync operations.

Tests POST /v0/projects/{project_id}/tasks/bulk and
PUT /v0/projects/{project_id}/tasks/sync endpoints.
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
def test_project(app: Flask, company_id: str) -> Project:
    """Create test project for task testing.

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
            start_date=datetime.now(UTC),
            finish_date=datetime.now(UTC) + timedelta(days=90),
            status="active",
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


class TestTaskBulkCreate:
    """Tests for POST /v0/projects/{project_id}/tasks/bulk endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_create_tasks_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test successful bulk task creation.

        Given: Valid array of task data
        When: POST /v0/projects/{id}/tasks/bulk is called
        Then: Returns 201 with all created tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "tasks": [
                {
                    "name": "Requirements Analysis",
                    "start": "2026-02-01T09:00:00Z",
                    "finish": "2026-02-15T18:00:00Z",
                    "wbs": "1.1",
                },
                {
                    "name": "Design Phase",
                    "start": "2026-02-16T09:00:00Z",
                    "finish": "2026-03-15T18:00:00Z",
                    "wbs": "1.2",
                },
                {
                    "name": "Implementation",
                    "start": "2026-03-16T09:00:00Z",
                    "finish": "2026-05-15T18:00:00Z",
                    "wbs": "1.3",
                },
            ]
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()

        assert data["data"]["created_count"] == 3
        assert data["data"]["failed_count"] == 0
        assert len(data["data"]["tasks"]) == 3
        assert "3 tasks created, 0 failed" in data["message"]

        # Verify database persistence
        with app.app_context():
            tasks = Task.query.filter_by(project_id=test_project.id).all()
            assert len(tasks) == 3

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_create_tasks_partial_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test bulk creation with validation error.

        Given: Array with valid and invalid task data
        When: POST /v0/projects/{id}/tasks/bulk is called
        Then: Returns 400 validation error (schema validates all items upfront)
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "tasks": [
                {
                    "name": "Valid Task 1",
                    "start": "2026-02-01T09:00:00Z",
                    "finish": "2026-02-15T18:00:00Z",
                },
                {
                    # Missing required name field
                    "start": "2026-02-16T09:00:00Z",
                    "finish": "2026-03-15T18:00:00Z",
                },
                {
                    "name": "Valid Task 2",
                    "start": "2026-03-16T09:00:00Z",
                    "finish": "2026-05-15T18:00:00Z",
                },
            ]
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        # Schema validation fails upfront when any task is invalid
        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "Validation failed"

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_create_tasks_exceeds_limit(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test bulk creation exceeding max batch size.

        Given: Array with more than 500 tasks
        When: POST /v0/projects/{id}/tasks/bulk is called
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create 501 tasks (exceeds limit of 500)
        tasks = []
        for i in range(501):
            tasks.append(
                {
                    "name": f"Task {i}",
                    "start": "2026-02-01T09:00:00Z",
                    "finish": "2026-02-15T18:00:00Z",
                }
            )

        payload = {"tasks": tasks}

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "Validation failed"

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_create_tasks_empty_array(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test bulk creation with empty task array.

        Given: Empty tasks array
        When: POST /v0/projects/{id}/tasks/bulk is called
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload: dict[str, list] = {"tasks": []}

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        assert response.status_code == 400

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_create_tasks_with_invalid_predecessors(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test bulk creation with invalid predecessor references.

        Given: Tasks with predecessor IDs that don't exist
        When: POST /v0/projects/{id}/tasks/bulk is called
        Then: Returns 201 but tracks invalid predecessors in errors
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create a valid task first
        with app.app_context():
            valid_task = Task(
                project_id=test_project.id,
                name="Existing Task",
                type="task",
                status="not_started",
                planned_start_date=datetime.now(UTC),
                planned_finish_date=datetime.now(UTC) + timedelta(days=5),
            )
            db.session.add(valid_task)
            db.session.commit()
            valid_task_id = valid_task.id

        # Create fake UUID for non-existent predecessor
        invalid_predecessor_id = str(uuid.uuid4())

        payload = {
            "tasks": [
                {
                    "name": "Task with Valid Predecessor",
                    "start": "2026-02-01T09:00:00Z",
                    "finish": "2026-02-15T18:00:00Z",
                    "wbs": "1.1",
                    "predecessors": [
                        {
                            "predecessor_task_id": str(valid_task_id),
                            "type": "FS",
                            "lag": 0,
                        }
                    ],
                },
                {
                    "name": "Task with Invalid Predecessor",
                    "start": "2026-02-16T09:00:00Z",
                    "finish": "2026-03-15T18:00:00Z",
                    "wbs": "1.2",
                    "predecessors": [
                        {
                            "predecessor_task_id": invalid_predecessor_id,
                            "type": "FS",
                            "lag": 0,
                        }
                    ],
                },
                {
                    "name": "Task with Multiple Invalid Predecessors",
                    "start": "2026-03-16T09:00:00Z",
                    "finish": "2026-05-15T18:00:00Z",
                    "wbs": "1.3",
                    "predecessors": [
                        {
                            "predecessor_task_id": str(uuid.uuid4()),
                            "type": "FS",
                            "lag": 0,
                        },
                        {
                            "predecessor_task_id": str(uuid.uuid4()),
                            "type": "FS",
                            "lag": 0,
                        },
                    ],
                },
            ]
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()

        # All tasks should be created
        assert data["data"]["created_count"] == 3

        # But errors should be tracked for invalid predecessors
        # The failed_count reflects tasks with errors (invalid predecessors)
        assert data["data"]["failed_count"] == 2  # Two tasks have invalid predecessors
        assert len(data["data"]["errors"]) == 2  # Two tasks have invalid predecessors

        # Verify error details
        errors = data["data"]["errors"]
        error_indices = [err["index"] for err in errors]
        assert 1 in error_indices  # Second task (index 1)
        assert 2 in error_indices  # Third task (index 2)

        # Verify error messages mention predecessors
        for error in errors:
            assert "predecessors" in error["errors"]
            assert "Invalid predecessor" in error["errors"]["predecessors"]

        # Verify all 3 tasks were created in the response
        assert len(data["data"]["tasks"]) == 3

        # Verify tasks were created in database
        with app.app_context():
            tasks = (
                Task.query.filter_by(project_id=test_project.id)
                .order_by(Task.name)
                .all()
            )
            # Should have: Existing Task + 3 new tasks = 4 total
            assert len(tasks) == 4


class TestTaskSync:
    """Tests for PUT /v0/projects/{project_id}/tasks/sync endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test sync with tasks that don't exist (not found).

        Given: Tasks do not exist in database
        When: PUT /v0/projects/{id}/tasks/sync is called
        Then: Returns 200 and tracks tasks as not_found
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "tasks": [
                {
                    "ms_project_uid": 101,
                    "name": "Non-existent Task 1",
                    "planned_start_date": "2026-02-01T09:00:00Z",
                    "planned_finish_date": "2026-02-15T18:00:00Z",
                },
                {
                    "ms_project_uid": 102,
                    "name": "Non-existent Task 2",
                    "planned_start_date": "2026-02-16T09:00:00Z",
                    "planned_finish_date": "2026-03-15T18:00:00Z",
                },
            ]
        }

        response = authenticated_client.put(
            f"/v0/projects/{test_project.id}/tasks/sync", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["updated_count"] == 0
        assert data["data"]["not_found_count"] == 2
        assert data["data"]["not_found_uids"] == [101, 102]
        assert "2 not found" in data["message"]

        # Verify tasks were NOT created
        with app.app_context():
            task1 = Task.query.filter_by(
                project_id=test_project.id, ms_project_uid=101
            ).first()
            task2 = Task.query.filter_by(
                project_id=test_project.id, ms_project_uid=102
            ).first()
            assert task1 is None
            assert task2 is None

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_update_existing(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test sync updates existing tasks.

        Given: Tasks with ms_project_uid exist
        When: PUT /v0/projects/{id}/tasks/sync with updated data
        Then: Returns 200 and updates existing tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create existing task
        with app.app_context():
            existing_task = Task(
                project_id=test_project.id,
                name="Original Name",
                ms_project_uid=101,
                type="task",
                status="not_started",
                planned_start_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 2, 15, 18, 0, tzinfo=UTC),
                percent_complete=0.0,
            )
            db.session.add(existing_task)
            db.session.commit()
            task_id = existing_task.id

        payload = {
            "tasks": [
                {
                    "ms_project_uid": 101,
                    "name": "Updated Name",
                    "planned_start_date": "2026-02-05T09:00:00Z",
                    "planned_finish_date": "2026-02-20T18:00:00Z",
                }
            ]
        }

        response = authenticated_client.put(
            f"/v0/projects/{test_project.id}/tasks/sync", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["updated_count"] == 1
        assert data["data"]["not_found_count"] == 0
        assert "1 tasks updated" in data["message"]

        # Verify update in database
        with app.app_context():
            updated_task = db.session.get(Task, task_id)
            assert updated_task is not None
            assert updated_task.name == "Updated Name"
            # Verify tracking data is preserved
            assert updated_task.status == "not_started"
            assert updated_task.percent_complete == pytest.approx(0.0)

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_mixed_operations(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test sync with mix of update and not_found.

        Given: Some tasks exist, some don't
        When: PUT /v0/projects/{id}/tasks/sync is called
        Then: Returns 200 with correct updated_count and not_found_count
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create one existing task
        with app.app_context():
            existing_task = Task(
                project_id=test_project.id,
                name="Existing Task",
                ms_project_uid=101,
                type="task",
                status="not_started",
                planned_start_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 2, 15, 18, 0, tzinfo=UTC),
            )
            db.session.add(existing_task)
            db.session.commit()

        payload = {
            "tasks": [
                {
                    "ms_project_uid": 101,
                    "name": "Updated Task",
                    "planned_start_date": "2026-02-05T09:00:00Z",
                    "planned_finish_date": "2026-02-20T18:00:00Z",
                },
                {
                    "ms_project_uid": 102,
                    "name": "Non-existent Task",
                    "planned_start_date": "2026-02-21T09:00:00Z",
                    "planned_finish_date": "2026-03-05T18:00:00Z",
                },
            ]
        }

        response = authenticated_client.put(
            f"/v0/projects/{test_project.id}/tasks/sync", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["updated_count"] == 1
        assert data["data"]["not_found_count"] == 1
        assert data["data"]["not_found_uids"] == [102]
        assert "1 tasks updated, 1 not found" in data["message"]

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_preserves_tracking_data(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test sync preserves tracking data.

        Given: Task exists with progress and actuals
        When: PUT /v0/projects/{id}/tasks/sync updates planning fields
        Then: Preserves percent_complete, actual_start, actual_finish
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create task with tracking data
        with app.app_context():
            task = Task(
                project_id=test_project.id,
                name="Task with Progress",
                ms_project_uid=101,
                type="task",
                status="in_progress",
                planned_start_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 2, 15, 18, 0, tzinfo=UTC),
                percent_complete=50.0,
                actual_start_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        payload = {
            "tasks": [
                {
                    "ms_project_uid": 101,
                    "name": "Updated Planning",
                    "planned_start_date": "2026-02-05T09:00:00Z",
                    "planned_finish_date": "2026-02-25T18:00:00Z",
                }
            ]
        }

        response = authenticated_client.put(
            f"/v0/projects/{test_project.id}/tasks/sync", json=payload
        )

        assert response.status_code == 200

        # Verify tracking data preserved
        with app.app_context():
            updated_task = db.session.get(Task, task_id)
            assert updated_task is not None
            assert updated_task.name == "Updated Planning"
            # Tracking data preserved
            assert updated_task.status == "in_progress"
            assert updated_task.percent_complete == pytest.approx(50.0)
            assert updated_task.actual_start_date is not None

    @patch("app.services.guardian_service.requests.post")
    def test_sync_tasks_recalculates_milestone_target_date(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test sync recalculates milestone target_date.

        Given: Milestone linked to tasks and one task finish date updated
        When: PUT /v0/projects/{id}/tasks/sync is called
        Then: Milestone target_date is recalculated and response includes details
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        initial_target_date = datetime(2026, 2, 20, 18, 0, tzinfo=UTC)
        task_early_finish = datetime(2026, 2, 15, 18, 0, tzinfo=UTC)
        task_late_finish = datetime(2026, 2, 20, 18, 0, tzinfo=UTC)
        new_finish = datetime(2026, 2, 25, 18, 0, tzinfo=UTC)

        with app.app_context():
            milestone = Milestone(
                project_id=test_project.id,
                name="Phase 1",
                target_date=initial_target_date,
                budget_weight=Decimal("0.2"),
                status="upcoming",
                is_achieved=False,
            )
            task_early = Task(
                project_id=test_project.id,
                name="Early Task",
                ms_project_uid=101,
                type="task",
                status="not_started",
                planned_start_date=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=task_early_finish,
            )
            task_late = Task(
                project_id=test_project.id,
                name="Late Task",
                ms_project_uid=102,
                type="task",
                status="not_started",
                planned_start_date=datetime(2026, 2, 5, 9, 0, tzinfo=UTC),
                planned_finish_date=task_late_finish,
            )

            db.session.add_all([milestone, task_early, task_late])
            db.session.commit()

            db.session.add_all(
                [
                    MilestoneTask(milestone_id=milestone.id, task_id=task_early.id),
                    MilestoneTask(milestone_id=milestone.id, task_id=task_late.id),
                ]
            )
            db.session.commit()

            milestone_id = milestone.id
            task_early_id = task_early.id
            old_target = milestone.target_date

        payload = {
            "tasks": [
                {
                    "ms_project_uid": 101,
                    "planned_finish_date": "2026-02-25T18:00:00Z",
                }
            ]
        }

        response = authenticated_client.put(
            f"/v0/projects/{test_project.id}/tasks/sync", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["milestone_recalculated_count"] == 1
        recalculated = data["data"]["recalculated_milestones"]
        assert len(recalculated) == 1
        assert recalculated[0]["milestone_id"] == str(milestone_id)
        assert recalculated[0]["critical_task_id"] == str(task_early_id)
        assert recalculated[0]["critical_task_name"] == "Early Task"

        expected_old = old_target.isoformat() if old_target else None
        expected_new = new_finish.replace(tzinfo=None).isoformat()
        assert recalculated[0]["old_target_date"] == expected_old
        assert recalculated[0]["new_target_date"] == expected_new

        with app.app_context():
            refreshed = db.session.get(Milestone, milestone_id)
            assert refreshed is not None
            assert refreshed.target_date == new_finish.replace(tzinfo=None)
