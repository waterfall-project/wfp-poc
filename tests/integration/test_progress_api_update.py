# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for bulk progress update endpoint."""

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
    """Create a project for progress update integration tests."""
    with app.app_context():
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Integration Progress Project",
            code="INT-PROG",
            start_date=datetime.now(UTC) - timedelta(days=5),
            finish_date=datetime.now(UTC) + timedelta(days=30),
            status="active",
            budget=75000.0,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def tasks(app: Flask, project: Project) -> list[Task]:
    """Create tasks for progress update integration tests."""
    with app.app_context():
        tasks = [
            Task(
                project_id=project.id,
                name="Integration Task A",
                status="not_started",
                percent_complete=0,
            ),
            Task(
                project_id=project.id,
                name="Integration Task B",
                status="in_progress",
                percent_complete=30,
            ),
        ]
        for task in tasks:
            db.session.add(task)
        db.session.commit()
        for task in tasks:
            db.session.refresh(task)
        return tasks


def test_progress_update_success(
    integration_client: FlaskClient,
    project: Project,
    tasks: list[Task],
) -> None:
    """Test bulk progress update success."""
    payload = {
        "date": datetime.now(UTC).isoformat(),
        "updates": [
            {"task_id": str(tasks[0].id), "percent_complete": 60},
            {"task_id": str(tasks[1].id), "percent_complete": 100},
        ],
    }

    response = integration_client.post(
        f"/v0/projects/{project.id}/progress",
        json=payload,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["data"]["updated_count"] == 2
    assert data["data"]["failed_count"] == 0
