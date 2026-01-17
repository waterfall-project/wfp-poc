# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for bulk progress update endpoint."""

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
def project_data(app: Flask, company_id: str) -> Project:
    """Create a sample project for progress updates."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Progress Project",
            code="PROG-001",
            start_date=datetime.now(UTC) - timedelta(days=10),
            finish_date=datetime.now(UTC) + timedelta(days=30),
            status="active",
            budget=50000.00,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def tasks_data(app: Flask, project_data: Project) -> list[Task]:
    """Create sample tasks for progress updates."""
    with app.app_context():
        tasks = [
            Task(
                project_id=project_data.id,
                name="Task A",
                status="not_started",
                percent_complete=0,
            ),
            Task(
                project_id=project_data.id,
                name="Task B",
                status="in_progress",
                percent_complete=20,
            ),
        ]
        for task in tasks:
            db.session.add(task)
        db.session.commit()
        for task in tasks:
            db.session.refresh(task)
        return tasks


class TestProjectProgressResource:
    """Tests for POST /v0/projects/{project_id}/progress endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_progress_update_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test successful bulk progress update.

        Given: Valid progress updates
        When: POST progress is called
        Then: Returns 200 with update results
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "date": datetime.now(UTC).isoformat(),
            "updates": [
                {
                    "task_id": str(tasks_data[0].id),
                    "percent_complete": 50,
                    "comment": "Halfway",
                },
                {
                    "task_id": str(tasks_data[1].id),
                    "percent_complete": 100,
                    "comment": "Done",
                },
            ],
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/progress",
            json=payload,
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["updated_count"] == 2
        assert data["data"]["failed_count"] == 0
        assert len(data["data"]["updates"]) == 2
        assert data["data"]["updates"][0]["new_percent_complete"] == 50

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_progress_update_partial_failure(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test partial success when one task is invalid.

        Given: One valid task and one invalid task
        When: POST progress is called
        Then: Returns 200 with errors for failed task
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "date": datetime.now(UTC).isoformat(),
            "updates": [
                {
                    "task_id": str(tasks_data[0].id),
                    "percent_complete": 40,
                },
                {
                    "task_id": str(uuid.uuid4()),
                    "percent_complete": 10,
                },
            ],
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/progress",
            json=payload,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["updated_count"] == 1
        assert data["data"]["failed_count"] == 1
        assert len(data["data"]["errors"]) == 1

    @patch("app.services.guardian_service.requests.post")
    def test_bulk_progress_update_completed_task(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        project_data: Project,
    ) -> None:
        """Test update on completed task returns 422.

        Given: Task is completed
        When: POST progress is called
        Then: Returns 422
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            task = Task(
                project_id=project_data.id,
                name="Completed Task",
                status="completed",
                percent_complete=100,
            )
            db.session.add(task)
            db.session.commit()
            db.session.refresh(task)

        payload = {
            "date": datetime.now(UTC).isoformat(),
            "updates": [
                {
                    "task_id": str(task.id),
                    "percent_complete": 90,
                }
            ],
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/progress",
            json=payload,
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "completed" in data["message"].lower()

    def test_bulk_progress_update_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test progress update without authentication.

        Given: No authentication token
        When: POST progress is called
        Then: Returns 401
        """
        payload = {
            "date": datetime.now(UTC).isoformat(),
            "updates": [],
        }

        response = client.post(
            f"/v0/projects/{project_data.id}/progress",
            json=payload,
        )

        assert response.status_code == 401
