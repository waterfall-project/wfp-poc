# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for ProjectListResource GET endpoint.

Tests project listing with pagination, filtering, sorting, and
authorization checks.
"""

# mypy: disable-error-code="call-arg"

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.project import Project
from app.models.task import Task

DEFAULT_START = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


@pytest.fixture
def projects_data(app: Flask, company_id: str) -> list[Project]:
    """Create sample projects for testing.

    Args:
        app: Flask application fixture.
        company_id: Company UUID for test isolation.

    Returns:
        List of created project instances.
    """
    with app.app_context():
        projects = [
            Project(
                company_id=uuid.UUID(company_id),
                name="Alpha Project",
                code="ALPHA-001",
                start_date=datetime.now(UTC) - timedelta(days=30),
                finish_date=datetime.now(UTC) + timedelta(days=60),
                status="active",
                budget=100000.00,
            ),
            Project(
                company_id=uuid.UUID(company_id),
                name="Beta Project",
                code="BETA-002",
                start_date=datetime.now(UTC) - timedelta(days=15),
                finish_date=datetime.now(UTC) + timedelta(days=45),
                status="active",
                budget=250000.00,
            ),
            Project(
                company_id=uuid.UUID(company_id),
                name="Gamma Project",
                code="GAMMA-003",
                start_date=datetime.now(UTC) - timedelta(days=60),
                finish_date=datetime.now(UTC) - timedelta(days=10),
                status="completed",
                budget=75000.00,
            ),
            Project(
                company_id=uuid.UUID(company_id),
                name="Delta Project",
                code="DELTA-004",
                start_date=datetime.now(UTC) + timedelta(days=10),
                finish_date=datetime.now(UTC) + timedelta(days=90),
                status="on_hold",
            ),
        ]

        for project in projects:
            db.session.add(project)
        db.session.commit()

        # Refresh to get generated IDs and timestamps
        for project in projects:
            db.session.refresh(project)

        return projects


class TestProjectListGet:
    """Tests for GET /v0/projects endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test successful project listing.

        Given: Multiple projects exist for company
        When: GET /v0/projects is called
        Then: Returns 200 with paginated list
        """
        # Mock Guardian to allow access
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects")

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
        assert data["total_pages"] == 1
        assert len(data["data"]) == 4

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_pagination(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test pagination parameters.

        Given: Multiple projects exist
        When: Requesting with page=1&per_page=2
        Then: Returns only 2 projects with correct pagination
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?page=1&per_page=2")

        assert response.status_code == 200
        data = response.get_json()

        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total"] == 4
        assert data["total_pages"] == 2
        assert len(data["data"]) == 2

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_filter_by_status(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test filtering by status.

        Given: Projects with different statuses
        When: Filtering by status=active
        Then: Returns only active projects
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?status=active")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 2
        for project in data["data"]:
            assert project["status"] == "active"

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_search(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test search functionality.

        Given: Projects with various names
        When: Searching for "Alpha"
        Then: Returns only matching projects
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?search=Alpha")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 1
        assert "Alpha" in data["data"][0]["name"]

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_sort_by_name_asc(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test sorting by name ascending.

        Given: Projects with different names
        When: Sorting by name in ascending order
        Then: Returns projects sorted alphabetically
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?sort_by=name&sort_order=asc")

        assert response.status_code == 200
        data = response.get_json()

        names = [p["name"] for p in data["data"]]
        assert names == sorted(names)
        assert names[0] == "Alpha Project"

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_invalid_status(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test invalid status parameter.

        Given: Valid authentication
        When: Requesting with invalid status
        Then: Returns 400 Bad Request
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?status=invalid")

        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid status" in data["message"]

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_invalid_pagination(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test invalid pagination parameters.

        Given: Valid authentication
        When: Requesting with invalid page number
        Then: Returns 400 Bad Request
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?page=invalid")

        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid pagination parameters" in data["message"]

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_per_page_max_100(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        projects_data: list[Project],
    ) -> None:
        """Test per_page maximum limit.

        Given: Request with per_page > 100
        When: GET /v0/projects called
        Then: Returns with per_page capped at 100
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects?per_page=200")

        assert response.status_code == 200
        data = response.get_json()
        assert data["per_page"] == 100

    def test_list_projects_no_auth(self, client: FlaskClient) -> None:
        """Test listing without authentication.

        Given: No JWT token provided
        When: GET /v0/projects is called
        Then: Returns 401 Unauthorized
        """
        response = client.get("/v0/projects")

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Unauthorized"

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_no_permission(
        self, mock_guardian: MagicMock, authenticated_client: FlaskClient
    ) -> None:
        """Test listing without permission.

        Given: Valid JWT but Guardian denies access
        When: GET /v0/projects is called
        Then: Returns 403 Forbidden
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_granted": False,
            "reason": "no_permission",
        }
        mock_guardian.return_value = mock_response

        response = authenticated_client.get("/v0/projects")

        assert response.status_code == 403

    @patch("app.services.guardian_service.requests.post")
    def test_list_projects_tenant_isolation(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        projects_data: list[Project],
        generate_jwt: Callable,
    ) -> None:
        """Test tenant isolation.

        Given: Projects for different companies
        When: User from company A requests projects
        Then: Returns only company A's projects
        """
        # Create project for different company
        other_company_id = str(uuid.uuid4())
        with app.app_context():
            other_project = Project(
                company_id=uuid.UUID(other_company_id),
                name="Other Company Project",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(other_project)
            db.session.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Use authenticated client with specific company_id
        with app.test_client() as client:
            token = generate_jwt(
                {
                    "user_id": "tenant-user",
                    "company_id": str(projects_data[0].company_id),
                    "email": "tenant@example.com",
                }
            )
            client.set_cookie("access_token", token)

            response = client.get("/v0/projects")

            assert response.status_code == 200
            data = response.get_json()

            # Should only see projects for the authenticated company
            assert data["total"] == 4
            for project in data["data"]:
                assert project["company_id"] == str(projects_data[0].company_id)


class TestProjectCrud:
    """Tests for project CRUD endpoints."""

    @patch("app.services.guardian_service.requests.post")
    def test_create_project_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test successful project creation."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        payload = {
            "name": "New Project",
            "code": "NEW-001",
            "start_date": DEFAULT_START.isoformat(),
            "finish_date": DEFAULT_FINISH.isoformat(),
        }

        response = authenticated_client.post("/v0/projects", json=payload)

        assert response.status_code == 201
        data = response.get_json()
        assert data["data"]["name"] == "New Project"
        assert data["data"]["currency_code"] == "EUR"

        with app.app_context():
            assert (
                Project.query.filter_by(company_id=uuid.UUID(company_id)).count() == 1
            )

    @patch("app.services.guardian_service.requests.post")
    def test_create_project_conflict(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test project creation conflict on duplicate code."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Existing",
                code="DUP-001",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()

        payload = {
            "name": "Duplicate",
            "code": "DUP-001",
            "start_date": DEFAULT_START.isoformat(),
            "finish_date": DEFAULT_FINISH.isoformat(),
        }

        response = authenticated_client.post("/v0/projects", json=payload)

        assert response.status_code == 409
        data = response.get_json()
        assert "already exists" in data["message"]

    @patch("app.services.guardian_service.requests.post")
    def test_get_project_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test retrieving a single project."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Fetch Me",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = authenticated_client.get(f"/v0/projects/{project_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["id"] == project_id
        assert data["data"]["name"] == "Fetch Me"

    @patch("app.services.guardian_service.requests.post")
    def test_get_project_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test retrieving a non-existent project returns 404."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(f"/v0/projects/{uuid.uuid4()}")

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_patch_project_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test partially updating a project."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Patch Me",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        new_finish = DEFAULT_FINISH + timedelta(days=10)
        payload = {"name": "Patched", "finish_date": new_finish.isoformat()}

        response = authenticated_client.patch(
            f"/v0/projects/{project_id}", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["name"] == "Patched"
        assert data["data"]["finish_date"].startswith(
            new_finish.replace(tzinfo=None).isoformat()
        )

    @patch("app.services.guardian_service.requests.post")
    def test_patch_project_invalid_dates(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test patch validation when finish_date is before start_date."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Invalid Patch",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        payload = {"finish_date": (DEFAULT_START - timedelta(days=1)).isoformat()}

        response = authenticated_client.patch(
            f"/v0/projects/{project_id}", json=payload
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "finish_date must be after start_date" in data["message"]

    @patch("app.services.guardian_service.requests.post")
    def test_delete_project_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test deleting a project without related entities."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Disposable",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = authenticated_client.delete(f"/v0/projects/{project_id}")

        assert response.status_code == 204

        with app.app_context():
            assert (
                Project.query.filter_by(company_id=uuid.UUID(company_id)).count() == 0
            )

    @patch("app.services.guardian_service.requests.post")
    def test_delete_project_with_tasks_conflict(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
    ) -> None:
        """Test deleting a project with related tasks returns 409."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Has Tasks",
                start_date=DEFAULT_START,
                finish_date=DEFAULT_FINISH,
            )
            db.session.add(project)
            db.session.commit()

            task = Task(
                project_id=project.id,
                name="Child Task",
                type="task",
                status="not_started",
            )
            db.session.add(task)
            db.session.commit()
            project_id = str(project.id)

        response = authenticated_client.delete(f"/v0/projects/{project_id}")

        assert response.status_code == 409
        data = response.get_json()
        assert "Cannot delete project" in data["message"]
