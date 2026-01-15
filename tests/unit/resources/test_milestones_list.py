# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for MilestoneListResource endpoints.

Tests milestone listing and creation with pagination, filtering,
authorization checks, and budget_weight validation.
"""

# mypy: disable-error-code="call-arg"

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.db import db
from app.models.milestone import Milestone
from app.models.project import Project


@pytest.fixture
def project_data(app: Flask, company_id: str) -> Project:
    """Create a sample project for milestone testing.

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
            start_date=datetime.now(UTC) - timedelta(days=30),
            finish_date=datetime.now(UTC) + timedelta(days=60),
            status="active",
            budget=100000.00,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project


@pytest.fixture
def milestones_data(app: Flask, project_data: Project) -> list[Milestone]:
    """Create sample milestones for testing.

    Args:
        app: Flask application fixture.
        project_data: Project fixture.

    Returns:
        List of created milestone instances.
    """
    with app.app_context():
        milestones = [
            Milestone(
                project_id=project_data.id,
                name="Requirements Review",
                description="Complete requirements specification review",
                target_date=datetime.now(UTC) + timedelta(days=10),
                budget_weight=Decimal("0.15"),
                status="upcoming",
                is_achieved=False,
            ),
            Milestone(
                project_id=project_data.id,
                name="Design Approval",
                description="Design phase completion",
                target_date=datetime.now(UTC) + timedelta(days=20),
                budget_weight=Decimal("0.25"),
                status="upcoming",
                is_achieved=False,
            ),
            Milestone(
                project_id=project_data.id,
                name="Development Complete",
                description="All development tasks finished",
                target_date=datetime.now(UTC) + timedelta(days=40),
                budget_weight=Decimal("0.40"),
                status="upcoming",
                is_achieved=False,
            ),
            Milestone(
                project_id=project_data.id,
                name="Testing Complete",
                description="All testing completed",
                target_date=datetime.now(UTC) - timedelta(days=5),
                actual_date=datetime.now(UTC) - timedelta(days=5),
                achieved_date=datetime.now(UTC) - timedelta(days=5),
                budget_weight=Decimal("0.20"),
                status="achieved",
                is_achieved=True,
            ),
        ]

        for milestone in milestones:
            db.session.add(milestone)
        db.session.commit()

        for milestone in milestones:
            db.session.refresh(milestone)

        return milestones


class TestMilestoneListGet:
    """Tests for GET /v0/projects/{project_id}/milestones endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_list_milestones_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test successful milestone listing.

        Given: Multiple milestones exist for project
        When: GET /v0/projects/{project_id}/milestones is called
        Then: Returns 200 with paginated list
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones"
        )

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
    def test_list_milestones_pagination(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test pagination parameters.

        Given: Multiple milestones exist
        When: Requesting with page=1&per_page=2
        Then: Returns only 2 milestones with correct pagination
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones?page=1&per_page=2"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["total"] == 4
        assert data["total_pages"] == 2
        assert len(data["data"]) == 2

    @patch("app.services.guardian_service.requests.post")
    def test_list_milestones_filter_by_status(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test filtering by status.

        Given: Milestones with different statuses exist
        When: Filtering by status=achieved
        Then: Returns only achieved milestones
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones?status=achieved"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 1
        assert all(m["status"] == "achieved" for m in data["data"])

    @patch("app.services.guardian_service.requests.post")
    def test_list_milestones_search(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test text search filtering.

        Given: Milestones with different names
        When: Searching with search=Design
        Then: Returns only milestones matching search term
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones?search=Design"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 1
        assert "Design" in data["data"][0]["name"]

    @patch("app.services.guardian_service.requests.post")
    def test_list_milestones_sort_by_target_date(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test sorting by target_date.

        Given: Milestones with different target dates
        When: Sorting by target_date desc
        Then: Returns milestones in descending order
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones?sort_by=target_date&sort_order=desc"
        )

        assert response.status_code == 200
        data = response.get_json()

        target_dates = [m["target_date"] for m in data["data"]]
        assert target_dates == sorted(target_dates, reverse=True)

    @patch("app.services.guardian_service.requests.post")
    def test_list_milestones_project_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test listing milestones for non-existent project.

        Given: Project does not exist
        When: GET /v0/projects/{invalid_id}/milestones is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_project_id = uuid.uuid4()
        response = authenticated_client.get(
            f"/v0/projects/{fake_project_id}/milestones"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_list_milestones_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test listing milestones without authentication.

        Given: No authentication token provided
        When: GET /v0/projects/{project_id}/milestones is called
        Then: Returns 401
        """
        response = client.get(f"/v0/projects/{project_data.id}/milestones")

        assert response.status_code == 401


class TestMilestoneListPost:
    """Tests for POST /v0/projects/{project_id}/milestones endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_create_milestone_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test successful milestone creation.

        Given: Valid milestone data with budget_weight
        When: POST /v0/projects/{project_id}/milestones is called
        Then: Returns 201 with created milestone
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        milestone_data = {
            "name": "Phase 1 Complete",
            "description": "First phase completion",
            "target_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "budget_weight": 0.3,
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 201
        data = response.get_json()

        assert "data" in data
        assert "message" in data
        assert data["data"]["name"] == milestone_data["name"]
        assert float(data["data"]["budget_weight"]) == milestone_data["budget_weight"]
        assert data["data"]["status"] == "upcoming"
        assert data["data"]["is_achieved"] is False

    @patch("app.services.guardian_service.requests.post")
    def test_create_milestone_budget_weight_exceeded(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestones_data: list[Milestone],
    ) -> None:
        """Test budget_weight sum validation.

        Given: Existing milestones sum to 1.0
        When: Creating new milestone with any budget_weight
        Then: Returns 409 conflict
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        milestone_data = {
            "name": "Extra Milestone",
            "target_date": (datetime.now(UTC) + timedelta(days=50)).isoformat(),
            "budget_weight": 0.1,
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "budget_weight" in data["message"].lower()

    @patch("app.services.guardian_service.requests.post")
    def test_create_milestone_invalid_budget_weight(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test budget_weight range validation.

        Given: budget_weight > 1.0
        When: Creating milestone
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        milestone_data = {
            "name": "Invalid Milestone",
            "target_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "budget_weight": 1.5,
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    @patch("app.services.guardian_service.requests.post")
    def test_create_milestone_missing_required_fields(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test validation with missing required fields.

        Given: Missing name field
        When: Creating milestone
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        milestone_data = {
            "target_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "budget_weight": 0.3,
        }

        response = authenticated_client.post(
            f"/v0/projects/{project_data.id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    @patch("app.services.guardian_service.requests.post")
    def test_create_milestone_project_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Test creating milestone for non-existent project.

        Given: Project does not exist
        When: POST milestone is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_project_id = uuid.uuid4()
        milestone_data = {
            "name": "Test Milestone",
            "target_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "budget_weight": 0.3,
        }

        response = authenticated_client.post(
            f"/v0/projects/{fake_project_id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 404

    def test_create_milestone_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test creating milestone without authentication.

        Given: No authentication token
        When: POST milestone is called
        Then: Returns 401
        """
        milestone_data = {
            "name": "Test Milestone",
            "target_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "budget_weight": 0.3,
        }

        response = client.post(
            f"/v0/projects/{project_data.id}/milestones",
            json=milestone_data,
        )

        assert response.status_code == 401
