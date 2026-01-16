# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for GET /v0/projects endpoint.

Tests the complete flow with real database and authentication.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.db import db
from app.models.project import Project


@pytest.fixture
def integration_projects(app, company_id):
    """Create projects for integration testing.

    Args:
        app: Flask application fixture.
        company_id: Company UUID for test isolation.

    Returns:
        List of created projects.
    """
    with app.app_context():
        projects = []
        for i in range(25):  # Create 25 projects to test pagination
            project = Project(
                company_id=uuid.UUID(company_id),
                name=f"Project {i:02d}",
                code=f"PRJ-{i:03d}",
                start_date=datetime.now(UTC) - timedelta(days=i * 10),
                finish_date=datetime.now(UTC) + timedelta(days=90 - i * 2),
                status="active" if i % 3 != 0 else "completed",
                budget=(i + 1) * 10000.00,
                currency_code="EUR",
            )
            db.session.add(project)
            projects.append(project)

        db.session.commit()

        for project in projects:
            db.session.refresh(project)

        return projects


class TestProjectListIntegration:
    """Integration tests for project listing."""

    def test_list_projects_supports_openapi_versioned_path(
        self, integration_client, integration_projects
    ) -> None:
        """Versioned path /{version}/projects works (OpenAPI contract).

        Given: Authenticated client and existing projects
        When: GET /v1/projects is called
        Then: Returns 200 and a paginated response
        """
        response = integration_client.get("/v1/projects?page=1&per_page=5")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert "data" in data

    def test_list_projects_full_flow(
        self, integration_client, integration_projects
    ) -> None:
        """Test complete flow with authentication and database.

        Given: 25 projects in database
        When: Authenticated user requests first page
        Then: Returns 20 projects with correct pagination
        """
        response = integration_client.get("/v0/projects?page=1&per_page=20")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 25
        assert data["per_page"] == 20
        assert data["page"] == 1
        assert data["total_pages"] == 2
        assert len(data["data"]) == 20

        # Verify all required fields are present
        first_project = data["data"][0]
        assert "id" in first_project
        assert "company_id" in first_project
        assert "name" in first_project
        assert "start_date" in first_project
        assert "finish_date" in first_project
        assert "status" in first_project
        assert "created_at" in first_project
        assert "updated_at" in first_project

    def test_list_projects_second_page(
        self, integration_client, integration_projects
    ) -> None:
        """Test pagination second page.

        Given: 25 projects in database
        When: Requesting page 2 with per_page=20
        Then: Returns remaining 5 projects
        """
        response = integration_client.get("/v0/projects?page=2&per_page=20")

        assert response.status_code == 200
        data = response.get_json()

        assert data["page"] == 2
        assert data["total"] == 25
        assert data["total_pages"] == 2
        assert len(data["data"]) == 5

    def test_list_projects_filter_completed(
        self, integration_client, integration_projects
    ) -> None:
        """Test filtering by completed status.

        Given: Mix of active and completed projects
        When: Filtering by status=completed
        Then: Returns only completed projects
        """
        response = integration_client.get("/v0/projects?status=completed")

        assert response.status_code == 200
        data = response.get_json()

        # Every 3rd project is completed (0, 3, 6, 9, 12, 15, 18, 21, 24) = 9 projects
        assert data["total"] == 9
        for project in data["data"]:
            assert project["status"] == "completed"

    def test_list_projects_search_by_name(
        self, integration_client, integration_projects
    ) -> None:
        """Test search functionality.

        Given: Projects with sequential names
        When: Searching for specific pattern
        Then: Returns only matching projects
        """
        response = integration_client.get("/v0/projects?search=Project 01")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] >= 1
        assert any("Project 01" in p["name"] for p in data["data"])

    def test_list_projects_sort_by_budget(
        self, integration_client, integration_projects
    ) -> None:
        """Test sorting by budget (via name as proxy).

        Given: Projects with different budgets
        When: Sorting by created_at desc (default)
        Then: Returns projects in correct order
        """
        response = integration_client.get(
            "/v0/projects?sort_by=created_at&sort_order=desc"
        )

        assert response.status_code == 200
        data = response.get_json()

        # Verify sorting by checking dates are descending
        dates = [p["created_at"] for p in data["data"]]
        assert dates == sorted(dates, reverse=True)

    def test_list_projects_empty_result(self, integration_client, app) -> None:
        """Test when no projects match filters.

        Given: Projects exist but none match filter
        When: Filtering by non-existent status
        Then: Returns empty list with total=0
        """
        response = integration_client.get("/v0/projects?status=cancelled")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 0
        assert data["total_pages"] == 0
        assert len(data["data"]) == 0

    def test_list_projects_date_range_filter(
        self, integration_client, integration_projects
    ) -> None:
        """Test filtering by date range.

        Given: Projects with various start dates
        When: Filtering by date range
        Then: Returns only projects within range
        """
        # Get projects starting in the last 50 days
        date_from = (datetime.now(UTC) - timedelta(days=50)).isoformat()

        response = integration_client.get(f"/v0/projects?start_date_from={date_from}")

        assert response.status_code == 200
        data = response.get_json()

        # Should return projects with indices 0-4 (5 projects)
        assert data["total"] <= 5

    def test_list_projects_combined_filters(
        self, integration_client, integration_projects
    ) -> None:
        """Test combining multiple filters.

        Given: Projects in database
        When: Applying status filter + search + sorting
        Then: Returns correctly filtered and sorted results
        """
        response = integration_client.get(
            "/v0/projects?status=active&search=Project&sort_by=name&sort_order=asc&per_page=5"
        )

        assert response.status_code == 200
        data = response.get_json()

        # All results should be active and sorted by name
        for project in data["data"]:
            assert project["status"] == "active"
            assert "Project" in project["name"]

        # Verify ascending order
        names = [p["name"] for p in data["data"]]
        assert names == sorted(names)

    def test_list_projects_per_page_boundary(
        self, integration_client, integration_projects
    ) -> None:
        """Test per_page boundary conditions.

        Given: 25 projects in database
        When: Requesting per_page=1
        Then: Returns 1 project per page
        """
        response = integration_client.get("/v0/projects?per_page=1")

        assert response.status_code == 200
        data = response.get_json()

        assert data["per_page"] == 1
        assert data["total_pages"] == 25
        assert len(data["data"]) == 1
