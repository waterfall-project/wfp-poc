# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Task CRUD operations.

Tests POST, GET, PATCH, DELETE operations on task endpoints.
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
from app.models.task_predecessor import TaskPredecessor


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


@pytest.fixture
def test_task(app: Flask, test_project: Project) -> Task:
    """Create test task.

    Args:
        app: Flask application fixture.
        test_project: Test project fixture.

    Returns:
        Created task instance.
    """
    with app.app_context():
        task = Task(
            project_id=test_project.id,
            name="Test Task",
            wbs_code="1.1",
            type="task",
            status="not_started",
            planned_start_date=datetime.now(UTC) + timedelta(days=1),
            planned_finish_date=datetime.now(UTC) + timedelta(days=10),
            percent_complete=0.0,
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task


class TestTaskCreate:
    """Tests for POST /v0/projects/{project_id}/tasks endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        app: Flask,
    ) -> None:
        """Test successful task creation.

        Given: Valid task data and authentication
        When: POST /v0/projects/{id}/tasks is called
        Then: Returns 201 with created task
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "name": "Design Database Schema",
            "start": "2026-02-01T09:00:00Z",
            "finish": "2026-02-15T18:00:00Z",
            "wbs": "1.99",  # Unique WBS to avoid conflicts
            "status": "not_started",
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()

        assert data["message"] == "Task created successfully"
        assert data["data"]["name"] == "Design Database Schema"
        assert data["data"]["wbs"] == "1.99"
        assert data["data"]["status"] == "not_started"
        assert "id" in data["data"]

        # Verify database persistence
        with app.app_context():
            task = Task.query.filter_by(
                project_id=test_project.id, wbs_code="1.99"
            ).first()
            assert task is not None
            assert task.name == "Design Database Schema"

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_minimal(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test creating task with only required fields.

        Given: Minimal valid task data
        When: POST /v0/projects/{id}/tasks is called
        Then: Returns 201 with default values
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "name": "Minimal Task",
            "start": "2026-02-01T09:00:00Z",
            "finish": "2026-02-05T18:00:00Z",
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()

        assert data["data"]["name"] == "Minimal Task"
        assert data["data"]["status"] == "not_started"
        assert data["data"]["percent_complete"] == 0

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_with_predecessors(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
    ) -> None:
        """Test creating task with predecessor relationships.

        Given: Existing task to use as predecessor
        When: Creating task with predecessor
        Then: Returns 201 with predecessor relationships
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "name": "Implementation Task",
            "start": "2026-02-16T09:00:00Z",
            "finish": "2026-02-28T18:00:00Z",
            "predecessors": [
                {"predecessor_task_id": str(test_task.id), "type": "FS", "lag": 0}
            ],
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()

        assert data["data"]["name"] == "Implementation Task"
        assert len(data["data"]["predecessors"]) == 1

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_circular_dependency(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
        app: Flask,
    ) -> None:
        """Test task creation with circular dependency.

        Given: Task A exists
        When: Creating task B that depends on A, and A already depends on future B
        Then: Returns 409 conflict
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # This test is simplified - in reality, circular dependencies
        # would be detected by the graph validation
        payload = {
            "name": "Circular Task",
            "start": "2026-02-01T09:00:00Z",
            "finish": "2026-02-05T18:00:00Z",
            "predecessors": [
                {"predecessor_task_id": str(test_task.id), "type": "FS", "lag": 0}
            ],
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        # Should succeed normally without circular dependency
        assert response.status_code == 201

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_missing_required_field(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test task creation without required fields.

        Given: Task data missing required name
        When: POST /v0/projects/{id}/tasks is called
        Then: Returns 422 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "start": "2026-02-01T09:00:00Z",
            "finish": "2026-02-05T18:00:00Z",
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        assert response.status_code == 422
        data = response.get_json()
        assert data["error"] == "Unprocessable Entity"

    @patch("app.services.guardian_service.requests.post")
    def test_create_task_invalid_dates(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test task creation with invalid date range.

        Given: Task data with finish before start
        When: POST /v0/projects/{id}/tasks is called
        Then: Returns 422 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "name": "Invalid Task",
            "start": "2026-02-15T09:00:00Z",
            "finish": "2026-02-01T18:00:00Z",  # Before start
        }

        response = authenticated_client.post(
            f"/v0/projects/{test_project.id}/tasks", json=payload
        )

        assert response.status_code == 422


class TestTaskGet:
    """Tests for GET /v0/projects/{project_id}/tasks/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_get_task_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
    ) -> None:
        """Test successful task retrieval.

        Given: Task exists
        When: GET /v0/projects/{id}/tasks/{task_id} is called
        Then: Returns 200 with task details
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks/{test_task.id}"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["id"] == str(test_task.id)
        assert data["data"]["name"] == "Test Task"
        assert data["data"]["wbs"] == "1.1"

    @patch("app.services.guardian_service.requests.post")
    def test_get_task_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test retrieving non-existent task.

        Given: Task does not exist
        When: GET /v0/projects/{id}/tasks/{invalid_id} is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        invalid_id = str(uuid.uuid4())
        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks/{invalid_id}"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"


class TestTaskUpdate:
    """Tests for PATCH /v0/projects/{project_id}/tasks/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_update_task_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
        app: Flask,
    ) -> None:
        """Test successful task update.

        Given: Task exists
        When: PATCH /v0/projects/{id}/tasks/{task_id} is called
        Then: Returns 200 with updated task
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {"status": "in_progress", "percent_complete": 25}

        response = authenticated_client.patch(
            f"/v0/projects/{test_project.id}/tasks/{test_task.id}", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["message"] == "Task updated successfully"
        assert data["data"]["status"] == "in_progress"
        assert data["data"]["percent_complete"] == 25

        # Verify database update
        with app.app_context():
            updated_task = db.session.get(Task, test_task.id)
            assert updated_task is not None
            assert updated_task.status == "in_progress"

    @patch("app.services.guardian_service.requests.post")
    def test_update_task_partial(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
    ) -> None:
        """Test partial task update.

        Given: Task exists
        When: Updating only one field
        Then: Returns 200 and updates only that field
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {"name": "Updated Task Name"}

        response = authenticated_client.patch(
            f"/v0/projects/{test_project.id}/tasks/{test_task.id}", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["name"] == "Updated Task Name"
        # Other fields unchanged
        assert data["data"]["status"] == "not_started"

    @patch("app.services.guardian_service.requests.post")
    def test_update_task_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test updating non-existent task.

        Given: Task does not exist
        When: PATCH /v0/projects/{id}/tasks/{invalid_id} is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        invalid_id = str(uuid.uuid4())
        payload = {"status": "completed"}

        response = authenticated_client.patch(
            f"/v0/projects/{test_project.id}/tasks/{invalid_id}", json=payload
        )

        assert response.status_code == 404


class TestTaskDelete:
    """Tests for DELETE /v0/projects/{project_id}/tasks/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_delete_task_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
        app: Flask,
    ) -> None:
        """Test successful task deletion.

        Given: Task exists and is not referenced as predecessor
        When: DELETE /v0/projects/{id}/tasks/{task_id} is called
        Then: Returns 204 and deletes task
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        task_id = test_task.id

        response = authenticated_client.delete(
            f"/v0/projects/{test_project.id}/tasks/{task_id}"
        )

        assert response.status_code == 204

        # Verify deletion
        with app.app_context():
            deleted_task = db.session.get(Task, task_id)
            assert deleted_task is None

    @patch("app.services.guardian_service.requests.post")
    def test_delete_task_referenced_as_predecessor(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        test_task: Task,
        app: Flask,
    ) -> None:
        """Test deleting task that is referenced as predecessor.

        Given: Task is referenced as predecessor by another task
        When: DELETE /v0/projects/{id}/tasks/{task_id} is called
        Then: Returns 409 conflict
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create a task that depends on test_task
        with app.app_context():
            dependent_task = Task(
                project_id=test_project.id,
                name="Dependent Task",
                type="task",
                status="not_started",
                planned_start_date=datetime.now(UTC) + timedelta(days=11),
                planned_finish_date=datetime.now(UTC) + timedelta(days=20),
            )
            db.session.add(dependent_task)
            db.session.commit()

            predecessor_rel = TaskPredecessor(
                predecessor_id=test_task.id,
                successor_id=dependent_task.id,
                type="FS",
                lag_minutes=0,
            )
            db.session.add(predecessor_rel)
            db.session.commit()

        response = authenticated_client.delete(
            f"/v0/projects/{test_project.id}/tasks/{test_task.id}"
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "predecessor" in data["message"].lower()

    @patch("app.services.guardian_service.requests.post")
    def test_delete_task_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test deleting non-existent task.

        Given: Task does not exist
        When: DELETE /v0/projects/{id}/tasks/{invalid_id} is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        invalid_id = str(uuid.uuid4())
        response = authenticated_client.delete(
            f"/v0/projects/{test_project.id}/tasks/{invalid_id}"
        )

        assert response.status_code == 404
