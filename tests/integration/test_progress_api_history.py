# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for progress history endpoint."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import db
from app.models.project import Project
from app.models.task import Task


@pytest.fixture
def project(app: Flask, company_id: str) -> Project:
    """Create a project for progress history integration tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Integration Progress History Project",
            code="INT-HIST",
            start_date=datetime.now(UTC) - timedelta(days=5),
            finish_date=datetime.now(UTC) + timedelta(days=30),
            status="active",
            budget=80000.0,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def task(app: Flask, project: Project) -> Task:
    """Create a task for progress history integration tests."""
    with app.app_context():
        task = Task(
            project_id=project.id,
            name="Integration History Task",
            status="not_started",
            percent_complete=0,
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task


def test_progress_history_success(
    integration_client: FlaskClient,
    project: Project,
    task: Task,
) -> None:
    """Test progress history retrieval after updates."""
    update_payload = {
        "date": datetime.now(UTC).isoformat(),
        "updates": [
            {"task_id": str(task.id), "percent_complete": 20},
        ],
    }

    update_response = integration_client.post(
        f"/v0/projects/{project.id}/progress",
        json=update_payload,
    )
    assert update_response.status_code == 200

    history_response = integration_client.get(
        f"/v0/projects/{project.id}/progress/history"
    )

    assert history_response.status_code == 200
    data = history_response.get_json()
    assert data["total"] == 1
    assert data["data"][0]["task_id"] == str(task.id)
