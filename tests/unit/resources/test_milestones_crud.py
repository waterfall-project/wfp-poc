# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for MilestoneResource CRUD endpoints.

Tests milestone retrieval, update, and deletion operations with
authorization checks and validation.
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
from app.models.expense import Expense
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
def milestone_data(app: Flask, project_data: Project) -> Milestone:
    """Create a sample milestone for testing.

    Args:
        app: Flask application fixture.
        project_data: Project fixture.

    Returns:
        Created milestone instance.
    """
    with app.app_context():
        milestone = Milestone(
            project_id=project_data.id,
            name="Requirements Review",
            description="Complete requirements specification review",
            target_date=datetime.now(UTC) + timedelta(days=10),
            budget_weight=Decimal("0.25"),
            status="upcoming",
            is_achieved=False,
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone


@pytest.fixture
def multiple_milestones(app: Flask, project_data: Project) -> list[Milestone]:
    """Create multiple milestones for budget_weight validation.

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
                name="Milestone 1",
                target_date=datetime.now(UTC) + timedelta(days=10),
                budget_weight=Decimal("0.30"),
                status="upcoming",
                is_achieved=False,
            ),
            Milestone(
                project_id=project_data.id,
                name="Milestone 2",
                target_date=datetime.now(UTC) + timedelta(days=20),
                budget_weight=Decimal("0.40"),
                status="upcoming",
                is_achieved=False,
            ),
        ]

        for milestone in milestones:
            db.session.add(milestone)
        db.session.commit()

        for milestone in milestones:
            db.session.refresh(milestone)

        return milestones


class TestMilestoneResourceGet:
    """Tests for GET /v0/projects/{project_id}/milestones/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test successful milestone retrieval.

        Given: Milestone exists in database
        When: GET /v0/projects/{project_id}/milestones/{id} is called
        Then: Returns 200 with milestone data
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}"
        )

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert data["data"]["id"] == str(milestone_data.id)
        assert data["data"]["name"] == milestone_data.name
        assert data["data"]["description"] == milestone_data.description
        assert float(data["data"]["budget_weight"]) == pytest.approx(
            float(milestone_data.budget_weight)
        )
        assert data["data"]["status"] == milestone_data.status
        assert data["data"]["is_achieved"] == milestone_data.is_achieved

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test retrieving non-existent milestone.

        Given: Milestone does not exist
        When: GET milestone is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()
        response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones/{fake_milestone_id}"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    @patch("app.services.guardian_service.requests.post")
    def test_get_milestone_wrong_project(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        company_id: str,
        milestone_data: Milestone,
    ) -> None:
        """Test retrieving milestone with wrong project_id.

        Given: Milestone exists but belongs to different project
        When: GET milestone with wrong project_id
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create another project
        with app.app_context():
            other_project = Project(
                company_id=uuid.UUID(company_id),
                name="Other Project",
                code="OTHER-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
                status="active",
                budget=50000.00,
            )
            db.session.add(other_project)
            db.session.commit()
            db.session.refresh(other_project)

            response = authenticated_client.get(
                f"/v0/projects/{other_project.id}/milestones/{milestone_data.id}"
            )

        assert response.status_code == 404

    def test_get_milestone_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test retrieving milestone without authentication.

        Given: No authentication token
        When: GET milestone is called
        Then: Returns 401
        """
        response = client.get(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}"
        )

        assert response.status_code == 401


class TestMilestoneResourcePatch:
    """Tests for PATCH /v0/projects/{project_id}/milestones/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test successful milestone update.

        Given: Valid update data
        When: PATCH milestone is called
        Then: Returns 200 with updated milestone
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        update_data = {
            "name": "Updated Milestone Name",
            "description": "Updated description",
        }

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["name"] == update_data["name"]
        assert data["data"]["description"] == update_data["description"]

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_budget_weight(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test updating budget_weight.

        Given: New valid budget_weight
        When: PATCH milestone budget_weight
        Then: Returns 200 with updated weight
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        update_data = {"budget_weight": 0.40}

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert float(data["data"]["budget_weight"]) == update_data["budget_weight"]

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_budget_weight_exceeded(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        multiple_milestones: list[Milestone],
    ) -> None:
        """Test budget_weight sum validation on update.

        Given: Multiple milestones with total weight 0.70
        When: Updating first milestone weight to 0.40 (would total 1.10)
        Then: Returns 409 conflict
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        update_data = {"budget_weight": 0.80}

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{multiple_milestones[0].id}",
            json=update_data,
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "budget_weight" in data["message"].lower()

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_status_to_achieved(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test marking milestone as achieved.

        Given: Milestone is upcoming
        When: PATCH with is_achieved=True and achieved_date
        Then: Returns 200 and updates status
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        achieved_date = datetime.now(UTC)
        update_data = {
            "is_achieved": True,
            "achieved_date": achieved_date.isoformat(),
            "status": "achieved",
        }

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["is_achieved"] is True
        assert data["data"]["status"] == "achieved"
        assert data["data"]["achieved_date"] is not None

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test updating non-existent milestone.

        Given: Milestone does not exist
        When: PATCH milestone is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()
        update_data = {"name": "Updated Name"}

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{fake_milestone_id}",
            json=update_data,
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_update_milestone_invalid_data(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test update with invalid data.

        Given: Invalid budget_weight value
        When: PATCH milestone is called
        Then: Returns 400 validation error
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        update_data = {"budget_weight": 2.0}

        response = authenticated_client.patch(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}",
            json=update_data,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "errors" in data

    def test_update_milestone_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test updating milestone without authentication.

        Given: No authentication token
        When: PATCH milestone is called
        Then: Returns 401
        """
        update_data = {"name": "Updated Name"}

        response = client.patch(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}",
            json=update_data,
        )

        assert response.status_code == 401


class TestMilestoneResourceDelete:
    """Tests for DELETE /v0/projects/{project_id}/milestones/{id} endpoint."""

    @patch("app.services.guardian_service.requests.post")
    def test_delete_milestone_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test successful milestone deletion.

        Given: Milestone exists
        When: DELETE milestone is called
        Then: Returns 204 and milestone is deleted
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        milestone_id = milestone_data.id

        response = authenticated_client.delete(
            f"/v0/projects/{project_data.id}/milestones/{milestone_id}"
        )

        assert response.status_code == 204

        # Verify milestone is deleted
        get_response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones/{milestone_id}"
        )
        assert get_response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_delete_milestone_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project_data: Project,
    ) -> None:
        """Test deleting non-existent milestone.

        Given: Milestone does not exist
        When: DELETE milestone is called
        Then: Returns 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_milestone_id = uuid.uuid4()

        response = authenticated_client.delete(
            f"/v0/projects/{project_data.id}/milestones/{fake_milestone_id}"
        )

        assert response.status_code == 404

    def test_delete_milestone_unauthenticated(
        self,
        client: FlaskClient,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test deleting milestone without authentication.

        Given: No authentication token
        When: DELETE milestone is called
        Then: Returns 401
        """
        response = client.delete(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}"
        )

        assert response.status_code == 401

    @patch("app.services.guardian_service.requests.post")
    def test_delete_milestone_with_expenses_conflict(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        app: Flask,
        project_data: Project,
        milestone_data: Milestone,
    ) -> None:
        """Test deleting milestone with associated expenses.

        Given: Milestone has associated expenses
        When: DELETE milestone is called
        Then: Returns 409 with descriptive error message
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        # Create an expense associated with the milestone
        with app.app_context():
            expense = Expense(
                project_id=project_data.id,
                milestone_id=milestone_data.id,
                category="procurement",
                description="Test expense allocated to milestone",
                date=datetime.now(tz=UTC),
                amount=Decimal("1000.00"),
            )
            db.session.add(expense)
            db.session.commit()
            db.session.refresh(expense)

        response = authenticated_client.delete(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}"
        )

        assert response.status_code == 409
        assert response.json is not None
        assert response.json["error"] == "Conflict"
        assert "cannot delete milestone" in response.json["message"].lower()
        assert "expense" in response.json["message"].lower()

        # Verify milestone still exists
        get_response = authenticated_client.get(
            f"/v0/projects/{project_data.id}/milestones/{milestone_data.id}"
        )
        assert get_response.status_code == 200
