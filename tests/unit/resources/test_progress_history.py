# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for progress history endpoint."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.progress_update import ProgressUpdate
from app.models.project import Project
from app.models.task import Task


@pytest.fixture
def project_data(app: Flask, company_id: str) -> Project:
    """Create a sample project for progress history tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="History Project",
            code="HIST-001",
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
def task_data(app: Flask, project_data: Project) -> Task:
    """Create a sample task for progress history tests."""
    with app.app_context():
        task = Task(
            project_id=project_data.id,
            name="History Task",
            status="in_progress",
            percent_complete=50,
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task


@pytest.fixture
def progress_updates(
    app: Flask, project_data: Project, task_data: Task, user_claims
) -> None:
    """Create progress update history entries."""
    with app.app_context():
        entry = ProgressUpdate(
            project_id=project_data.id,
            task_id=task_data.id,
            update_date=datetime.now(UTC) - timedelta(days=1),
            previous_percent_complete=25,
            percent_complete=50,
            notes="Progress update",
            updated_by=uuid.UUID(user_claims["user_id"]),
        )
        db.session.add(entry)
        db.session.commit()


class TestProjectProgressHistoryResource:
    """Tests for GET /v0/projects/{project_id}/progress/history endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_progress_history_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        progress_updates: None,
    ) -> None:
        """Test fetching progress history.

        Given: Progress update history exists
        When: GET history is called
        Then: Returns 200 with history data
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/progress/history"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert len(data["data"]) == 1

    @patch("app.services.guardian_service.requests.post")
    def test_progress_history_filter_by_task(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        task_data: Task,
        progress_updates: None,
    ) -> None:
        """Test filtering history by task_id.

        Given: Progress updates for a task
        When: GET history with task_id filter
        Then: Returns only matching updates
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/progress/history?task_id={task_data.id}"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["data"][0]["task_id"] == str(task_data.id)

    def test_progress_history_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test progress history without authentication."""
        response = client.get(f"/v0/projects/{project_data.id}/progress/history")

        assert response.status_code == 401
