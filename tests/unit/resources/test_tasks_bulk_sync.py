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
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
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
        Then: Returns 422 validation error (schema validates all items upfront)
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
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"] == "Unprocessable Entity"

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
        Then: Returns 422 validation error
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

        assert response.status_code == 422
        data = response.get_json()
        assert data["error"] == "Unprocessable Entity"

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
        Then: Returns 422 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload: dict[str, list] = {"tasks": []}

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks/bulk", json=payload
        )

        assert response.status_code == 422


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
            assert updated_task.percent_complete == 0.0

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
            assert updated_task.percent_complete == 50.0
            assert updated_task.actual_start_date is not None
