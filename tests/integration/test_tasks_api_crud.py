# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for task endpoints.

Covers create, retrieve, update, delete, and list flows for
/v0/projects/{project_id}/tasks endpoints using the real stack.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.models.db import db
from app.models.project import Project
from app.models.task import Task


def _make_task(**kwargs: Any) -> Task:
    """Instantiate a Task and populate fields explicitly for mypy."""
    project_id = kwargs.pop("project_id")
    name = kwargs.pop("name")
    task = Task(project_id=project_id, name=name)
    for key, value in kwargs.items():
        setattr(task, key, value)
    return task


@pytest.fixture
def project(app, company_id):
    """Create a project scoped to the test company.

    Given: Company identifier from JWT fixture
    When: Project is created in the database
    Then: Project is persisted and returned for downstream tests
    """

    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Task Integration Project",
            code=f"TASK-{uuid.uuid4().hex[:8]}",
            start_date=datetime.now(UTC),
            finish_date=datetime.now(UTC) + timedelta(days=90),
            status="active",
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def task(app, project):
    """Create a baseline task for retrieval/update/delete tests."""

    with app.app_context():
        task = _make_task(
            project_id=project.id,
            name="Existing Task",
            type="task",
            status="not_started",
            wbs_code="1.0",
            planned_start_date=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
            planned_finish_date=datetime(2026, 1, 20, 18, 0, tzinfo=UTC),
            percent_complete=0.0,
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task


class TestTaskCreate:
    """Integration tests for POST /v0/projects/{project_id}/tasks."""

    def test_create_task_success(self, integration_client, app, project):
        """Test successful task creation.

        Given: Valid task payload for an existing project
        When: POST /v0/projects/{project_id}/tasks is called
        Then: Response is 201 and task persists with expected fields
        """

        payload = {
            "name": "Integration Task",
            "start": "2026-02-01T09:00:00Z",
            "finish": "2026-02-10T18:00:00Z",
            "wbs": "1.1",
            "status": "not_started",
        }

        response = integration_client.post(
            f"/v0/projects/{project.id}/tasks", json=payload
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "Task created successfully"
        assert data["data"]["name"] == "Integration Task"
        assert data["data"]["status"] == "not_started"
        assert data["data"]["wbs"] == "1.1"
        assert "id" in data["data"]

        with app.app_context():
            created = Task.query.filter_by(
                project_id=project.id, name="Integration Task"
            ).first()
            assert created is not None
            assert created.wbs_code == "1.1"

    def test_create_task_validation_error(self, integration_client, project):
        """Test validation error when required fields are missing.

        Given: Payload omits required scheduling fields
        When: POST /v0/projects/{project_id}/tasks is called
        Then: Response is 422 with validation errors including start
        """

        response = integration_client.post(
            f"/v0/projects/{project.id}/tasks", json={"name": "Incomplete"}
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "errors" in data
        assert "start" in str(data["errors"])


class TestTaskRetrieve:
    """Integration tests for GET /v0/projects/{project_id}/tasks/{id}."""

    def test_get_task_success(self, integration_client, task):
        """Test retrieving an existing task.

        Given: Task exists for the authenticated project
        When: GET /v0/projects/{project_id}/tasks/{id} is called
        Then: Response is 200 with matching task payload
        """

        response = integration_client.get(
            f"/v0/projects/{task.project_id}/tasks/{task.id}"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["id"] == str(task.id)
        assert data["data"]["name"] == "Existing Task"
        assert data["data"]["status"] == "not_started"

    def test_get_task_not_found(self, integration_client, project):
        """Test retrieving a non-existent task returns 404.

        Given: No task exists for the provided ID
        When: GET /v0/projects/{project_id}/tasks/{id} is called
        Then: Response is 404 with not found message
        """

        response = integration_client.get(
            f"/v0/projects/{project.id}/tasks/{uuid.uuid4()}"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Task not found"


class TestTaskUpdate:
    """Integration tests for PATCH /v0/projects/{project_id}/tasks/{id}."""

    def test_update_task_status_and_progress(self, integration_client, app, task):
        """Test updating status and percent_complete.

        Given: Task exists with initial status not_started
        When: PATCH /v0/projects/{project_id}/tasks/{id} updates status and progress
        Then: Response is 200 and persisted task reflects new values
        """

        payload = {
            "status": "in_progress",
            "percent_complete": 45,
        }

        response = integration_client.patch(
            f"/v0/projects/{task.project_id}/tasks/{task.id}", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Task updated successfully"
        assert data["data"]["status"] == "in_progress"
        assert data["data"]["percent_complete"] == 45

        with app.app_context():
            updated = db.session.get(Task, task.id)
            assert updated is not None
            assert updated.status == "in_progress"
            assert updated.percent_complete == 45

    def test_update_task_invalid_uuid(self, integration_client, project):
        """Test update with invalid UUID returns 400.

        Given: Invalid task ID format
        When: PATCH /v0/projects/{project_id}/tasks/{id} is called
        Then: Response is 400 with invalid UUID message
        """

        response = integration_client.patch(
            f"/v0/projects/{project.id}/tasks/invalid-uuid",
            json={"status": "completed"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["message"] == "Invalid UUID format"


class TestTaskDelete:
    """Integration tests for DELETE /v0/projects/{project_id}/tasks/{id}."""

    def test_delete_task_success(self, integration_client, app, project):
        """Test deleting an existing task.

        Given: Task exists for the project
        When: DELETE /v0/projects/{project_id}/tasks/{id} is called
        Then: Response is 204 and task is removed from database
        """

        with app.app_context():
            deletable = _make_task(
                project_id=project.id,
                name="Delete Me",
                type="task",
                status="not_started",
                planned_start_date=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
                planned_finish_date=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
                percent_complete=0.0,
            )
            db.session.add(deletable)
            db.session.commit()
            db.session.refresh(deletable)

        response = integration_client.delete(
            f"/v0/projects/{project.id}/tasks/{deletable.id}"
        )

        assert response.status_code == 204

        with app.app_context():
            removed = db.session.get(Task, deletable.id)
            assert removed is None


class TestTaskList:
    """Integration tests for GET /v0/projects/{project_id}/tasks listing."""

    def test_list_tasks_with_filters_and_pagination(
        self, integration_client, app, project
    ) -> None:
        """Test status filter and pagination on task list.

        Given: Multiple tasks with different statuses exist
        When: GET /v0/projects/{project_id}/tasks is called with status filter
        Then: Response is 200 with filtered results and pagination metadata
        """

        with app.app_context():
            tasks = [
                _make_task(
                    project_id=project.id,
                    name="Planned Task",
                    type="task",
                    status="not_started",
                    wbs_code="1.1",
                    planned_start_date=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
                    planned_finish_date=datetime(2026, 4, 5, 18, 0, tzinfo=UTC),
                    percent_complete=0.0,
                ),
                _make_task(
                    project_id=project.id,
                    name="Active Task",
                    type="task",
                    status="in_progress",
                    wbs_code="1.2",
                    planned_start_date=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
                    planned_finish_date=datetime(2026, 4, 15, 18, 0, tzinfo=UTC),
                    percent_complete=50.0,
                ),
                _make_task(
                    project_id=project.id,
                    name="Done Task",
                    type="task",
                    status="completed",
                    wbs_code="1.3",
                    planned_start_date=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
                    planned_finish_date=datetime(2026, 4, 20, 18, 0, tzinfo=UTC),
                    percent_complete=100.0,
                ),
            ]
            db.session.add_all(tasks)
            db.session.commit()

        response = integration_client.get(
            f"/v0/projects/{project.id}/tasks?status=completed&per_page=2&page=1"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "completed"
