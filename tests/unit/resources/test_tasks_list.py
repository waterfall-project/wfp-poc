# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for TaskListResource GET endpoint.

Tests task listing with pagination, filtering, sorting, and
authorization checks.
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


@pytest.fixture
def tasks_data(app: Flask, test_project: Project) -> list[Task]:
    """Create sample tasks for testing.

    Args:
        app: Flask application fixture.
        test_project: Test project fixture.

    Returns:
        List of created task instances.
    """
    with app.app_context():
        tasks = [
            Task(
                project_id=test_project.id,
                name="Requirements Analysis",
                wbs_code="1.1",
                type="task",
                status="completed",
                planned_start_date=datetime.now(UTC) - timedelta(days=30),
                planned_finish_date=datetime.now(UTC) - timedelta(days=20),
                percent_complete=100.0,
                is_critical=True,
            ),
            Task(
                project_id=test_project.id,
                name="Design Phase",
                wbs_code="1.2",
                type="task",
                status="in_progress",
                planned_start_date=datetime.now(UTC) - timedelta(days=15),
                planned_finish_date=datetime.now(UTC) + timedelta(days=15),
                percent_complete=50.0,
                is_critical=True,
            ),
            Task(
                project_id=test_project.id,
                name="Milestone: Design Complete",
                wbs_code="1.3",
                type="milestone",
                status="not_started",
                planned_start_date=datetime.now(UTC) + timedelta(days=15),
                planned_finish_date=datetime.now(UTC) + timedelta(days=15),
                percent_complete=0.0,
                is_critical=False,
            ),
            Task(
                project_id=test_project.id,
                name="Implementation",
                wbs_code="2.1",
                type="summary",
                status="not_started",
                planned_start_date=datetime.now(UTC) + timedelta(days=20),
                planned_finish_date=datetime.now(UTC) + timedelta(days=60),
                percent_complete=0.0,
                is_critical=False,
            ),
        ]

        for task in tasks:
            db.session.add(task)
        db.session.commit()

        for task in tasks:
            db.session.refresh(task)

        return tasks


class TestTaskListGet:
    """Tests for GET /v0/projects/{project_id}/tasks endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test successful task listing.

        Given: Multiple tasks exist for project
        When: GET /v0/projects/{id}/tasks is called
        Then: Returns 200 with paginated list
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(f"/v0/projects/{test_project.id}/tasks")

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "page" in data
        assert "per_page" in data
        assert "total" in data
        assert "total_pages" in data

        assert data["page"] == 1
        assert data["per_page"] == 20
        assert data["total"] == 4
        assert len(data["data"]) == 4

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_pagination(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test pagination parameters.

        Given: Multiple tasks exist
        When: Requesting with page=1&per_page=2
        Then: Returns only 2 tasks with correct pagination
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?page=1&per_page=2"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total"] == 4
        assert data["total_pages"] == 2
        assert len(data["data"]) == 2

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_filter_by_status(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test filtering by status.

        Given: Tasks with different statuses exist
        When: Filtering by status=in_progress
        Then: Returns only tasks with matching status
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?status=in_progress"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 1
        assert data["data"][0]["status"] == "in_progress"
        assert data["data"][0]["name"] == "Design Phase"

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_filter_by_is_milestone(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test filtering by is_milestone flag.

        Given: Tasks and milestones exist
        When: Filtering by is_milestone=true
        Then: Returns only milestone tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?is_milestone=true"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 1
        assert "Milestone" in data["data"][0]["name"]

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_filter_by_is_critical(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test filtering by critical path.

        Given: Tasks with different critical flags exist
        When: Filtering by is_critical=true
        Then: Returns only critical path tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?is_critical=true"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 2
        for task in data["data"]:
            assert task["is_critical"] is True

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_search(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test search in task name.

        Given: Tasks with different names exist
        When: Searching for "Design"
        Then: Returns matching tasks
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?search=Design"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] >= 1
        for task in data["data"]:
            assert "Design" in task["name"] or "design" in task["name"].lower()

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_sort_by_wbs(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
        tasks_data: list[Task],
    ) -> None:
        """Test sorting by WBS code.

        Given: Tasks with different WBS codes exist
        When: Sorting by wbs ascending
        Then: Returns tasks in WBS order
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{test_project.id}/tasks?sort_by=wbs&sort_order=asc"
        )

        assert response.status_code == 200
        data = response.get_json()

        wbs_codes = [task["wbs"] for task in data["data"] if task["wbs"]]
        assert wbs_codes == sorted(wbs_codes)

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_invalid_project_id(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test listing tasks for non-existent project.

        Given: Project does not exist
        When: GET /v0/projects/{invalid_id}/tasks is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        invalid_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/v0/projects/{invalid_id}/tasks")

        assert response.status_code == 404
        data = response.get_json()
        assert data["message"] == "Project not found"

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_no_auth(
        self,
        mock_guardian: MagicMock,
        client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test listing tasks without authentication.

        Given: No JWT token provided
        When: GET /v0/projects/{id}/tasks is called
        Then: Returns 401
        """
        response = client.get(f"/v0/projects/{test_project.id}/tasks")

        assert response.status_code == 401

    @patch("app.services.guardian_service.requests.post")
    def test_list_tasks_no_permission(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        test_project: Project,
    ) -> None:
        """Test listing tasks without permission.

        Given: User lacks LIST permission
        When: GET /v0/projects/{id}/tasks is called
        Then: Returns 403
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": False,
            "reason": "no_permission",
        }
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(f"/v0/projects/{test_project.id}/tasks")

        assert response.status_code == 403
