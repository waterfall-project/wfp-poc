# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for Project CRUD endpoints.

Tests POST, GET, PATCH, DELETE operations on /v0/projects with real
database and authentication.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.models.db import db
from app.models.project import Project
from app.models.task import Task


class TestProjectCreate:
    """Integration tests for POST /v0/projects endpoint."""

    def test_create_project_success(self, integration_client, app, company_id) -> None:
        """Test successful project creation.

        Given: Valid project data and authentication
        When: POST /v0/projects is called
        Then: Returns 201 with created project and persists to database
        """
        payload = {
            "name": "Integration Test Project",
            "code": "INT-001",
            "title": "Test Title",
            "start_date": "2026-01-15T09:00:00Z",
            "finish_date": "2026-12-31T18:00:00Z",
            "status": "active",
            "budget": 500000.00,
            "currency_code": "USD",
            "description": "Integration test project description",
        }

        response = integration_client.post("/v0/projects", json=payload)

        assert response.status_code == 201
        data = response.get_json()

        assert data["message"] == "Project created successfully"
        assert data["data"]["name"] == "Integration Test Project"
        assert data["data"]["code"] == "INT-001"
        assert data["data"]["status"] == "active"
        assert data["data"]["budget"] == 500000.00
        assert data["data"]["currency_code"] == "USD"
        assert "id" in data["data"]
        assert "created_at" in data["data"]
        assert "updated_at" in data["data"]

        # Verify database persistence
        with app.app_context():
            project = Project.query.filter_by(code="INT-001").first()
            assert project is not None
            assert project.name == "Integration Test Project"
            assert project.company_id == uuid.UUID(company_id)

    def test_create_project_minimal(self, integration_client, app, company_id) -> None:
        """Test creating project with only required fields.

        Given: Minimal valid project data (name, start_date, finish_date)
        When: POST /v0/projects is called
        Then: Returns 201 and applies default values
        """
        payload = {
            "name": "Minimal Project",
            "code": "MIN-001",
            "start_date": "2026-02-01T09:00:00Z",
            "finish_date": "2026-03-01T18:00:00Z",
        }

        response = integration_client.post("/v0/projects", json=payload)

        assert response.status_code == 201
        data = response.get_json()

        assert data["data"]["name"] == "Minimal Project"
        assert data["data"]["code"] == "MIN-001"
        assert data["data"]["status"] == "initialized"  # Default value
        assert data["data"]["currency_code"] == "EUR"  # Default value

    def test_create_project_duplicate_code(
        self, integration_client, app, company_id
    ) -> None:
        """Test project creation conflict on duplicate code.

        Given: Project with code already exists for company
        When: POST /v0/projects with duplicate code
        Then: Returns 409 conflict error
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Existing Project",
                code="DUP-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(project)
            db.session.commit()

        payload = {
            "name": "Duplicate Code Project",
            "code": "DUP-001",
            "start_date": "2026-02-01T09:00:00Z",
            "finish_date": "2026-03-01T18:00:00Z",
        }

        response = integration_client.post("/v0/projects", json=payload)

        assert response.status_code == 409
        data = response.get_json()
        assert "already exists" in data["message"]
        assert "DUP-001" in data["message"]

    def test_create_project_validation_error(self, integration_client) -> None:
        """Test project creation with invalid data.

        Given: Invalid project data (finish_date before start_date)
        When: POST /v0/projects is called
        Then: Returns 422 business rule error
        """
        payload = {
            "name": "Invalid Project",
            "code": "INV-001",
            "start_date": "2026-12-31T18:00:00Z",
            "finish_date": "2026-01-01T09:00:00Z",  # Before start_date
        }

        response = integration_client.post("/v0/projects", json=payload)

        assert response.status_code == 422
        data = response.get_json()
        assert data["error"] == "Unprocessable Entity"
        assert "finish_date must be after start_date" in data["message"]

    def test_create_project_missing_required_field(self, integration_client) -> None:
        """Test project creation without required fields.

        Given: Project data missing required name field
        When: POST /v0/projects is called
        Then: Returns 400 validation error
        """
        payload = {
            "code": "NO-NAME-001",
            "start_date": "2026-02-01T09:00:00Z",
            "finish_date": "2026-03-01T18:00:00Z",
        }

        response = integration_client.post("/v0/projects", json=payload)

        assert response.status_code == 400
        data = response.get_json()
        assert "name" in str(data["errors"])


class TestProjectRetrieve:
    """Integration tests for GET /v0/projects/{id} endpoint."""

    def test_get_project_success(self, integration_client, app, company_id) -> None:
        """Test retrieving a single project by ID.

        Given: Project exists in database
        When: GET /v0/projects/{id} is called
        Then: Returns 200 with complete project data
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Fetch Me Project",
                code="FETCH-001",
                title="Integration Test",
                start_date=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                finish_date=datetime(2026, 12, 31, 18, 0, tzinfo=UTC),
                status="active",
                budget=100000.00,
                currency_code="EUR",
                description="Test project for retrieval",
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = integration_client.get(f"/v0/projects/{project_id}")

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["id"] == project_id
        assert data["data"]["name"] == "Fetch Me Project"
        assert data["data"]["code"] == "FETCH-001"
        assert data["data"]["title"] == "Integration Test"
        assert data["data"]["status"] == "active"
        assert data["data"]["budget"] == 100000.00
        assert data["data"]["currency_code"] == "EUR"
        assert data["data"]["description"] == "Test project for retrieval"
        assert "created_at" in data["data"]
        assert "updated_at" in data["data"]

    def test_get_project_not_found(self, integration_client) -> None:
        """Test retrieving non-existent project.

        Given: Project ID does not exist
        When: GET /v0/projects/{id} is called
        Then: Returns 404 not found
        """
        non_existent_id = str(uuid.uuid4())

        response = integration_client.get(f"/v0/projects/{non_existent_id}")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"
        assert data["message"] == "Project not found"

    def test_get_project_invalid_uuid(self, integration_client) -> None:
        """Test retrieving project with invalid UUID format.

        Given: Invalid UUID string
        When: GET /v0/projects/{id} is called
        Then: Returns 404 (invalid UUID treated as not found)
        """
        response = integration_client.get("/v0/projects/invalid-uuid")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_get_project_wrong_company(
        self, integration_client, app, generate_uuid
    ) -> None:
        """Test retrieving project from different company.

        Given: Project exists for different company
        When: GET /v0/projects/{id} is called
        Then: Returns 404 (not accessible)
        """
        other_company_id = generate_uuid()

        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(other_company_id),
                name="Other Company Project",
                code="OTHER-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = integration_client.get(f"/v0/projects/{project_id}")

        assert response.status_code == 404


class TestProjectUpdate:
    """Integration tests for PATCH /v0/projects/{id} endpoint."""

    def test_patch_project_success(self, integration_client, app, company_id) -> None:
        """Test partially updating a project.

        Given: Project exists and valid update data
        When: PATCH /v0/projects/{id} is called
        Then: Returns 200 with updated project and persists changes
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Original Name",
                code="PATCH-001",
                start_date=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                finish_date=datetime(2026, 12, 31, 18, 0, tzinfo=UTC),
                status="active",
                budget=100000.00,
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        payload = {
            "name": "Updated Name",
            "status": "on_hold",
            "budget": 150000.00,
            "description": "Updated description",
        }

        response = integration_client.patch(f"/v0/projects/{project_id}", json=payload)

        assert response.status_code == 200
        data = response.get_json()

        assert data["message"] == "Project updated successfully"
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["status"] == "on_hold"
        assert data["data"]["budget"] == 150000.00
        assert data["data"]["description"] == "Updated description"
        assert data["data"]["code"] == "PATCH-001"  # Unchanged

        # Verify database persistence
        with app.app_context():
            updated_project = db.session.get(Project, uuid.UUID(project_id))
            assert updated_project is not None
            assert updated_project.name == "Updated Name"
            assert updated_project.status == "on_hold"
            assert updated_project.budget == 150000.00

    def test_patch_project_single_field(
        self, integration_client, app, company_id
    ) -> None:
        """Test updating single field.

        Given: Project exists
        When: PATCH /v0/projects/{id} with single field
        Then: Returns 200 and only updates specified field
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Original",
                code="SINGLE-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
                status="active",
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        payload = {"status": "completed"}

        response = integration_client.patch(f"/v0/projects/{project_id}", json=payload)

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["status"] == "completed"
        assert data["data"]["name"] == "Original"  # Unchanged
        assert data["data"]["code"] == "SINGLE-001"  # Unchanged

    def test_patch_project_dates(self, integration_client, app, company_id) -> None:
        """Test updating project dates.

        Given: Project exists
        When: PATCH /v0/projects/{id} with new dates
        Then: Returns 200 and updates dates
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Date Update Project",
                code="DATE-001",
                start_date=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                finish_date=datetime(2026, 6, 30, 18, 0, tzinfo=UTC),
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        payload = {
            "start_date": "2026-02-01T10:00:00Z",
            "finish_date": "2026-12-31T17:00:00Z",
        }

        response = integration_client.patch(f"/v0/projects/{project_id}", json=payload)

        assert response.status_code == 200
        data = response.get_json()

        assert "2026-02-01" in data["data"]["start_date"]
        assert "2026-12-31" in data["data"]["finish_date"]

    def test_patch_project_invalid_dates(
        self, integration_client, app, company_id
    ) -> None:
        """Test updating with invalid date range.

        Given: Project exists
        When: PATCH /v0/projects/{id} with finish_date before start_date
        Then: Returns 400 validation error
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Invalid Date Project",
                code="INV-DATE-001",
                start_date=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
                finish_date=datetime(2026, 12, 31, 18, 0, tzinfo=UTC),
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        payload = {"finish_date": "2026-01-01T09:00:00Z"}  # Before start_date

        response = integration_client.patch(f"/v0/projects/{project_id}", json=payload)

        assert response.status_code == 422
        data = response.get_json()
        assert "finish_date must be after start_date" in data["message"]

    def test_patch_project_not_found(self, integration_client) -> None:
        """Test updating non-existent project.

        Given: Project ID does not exist
        When: PATCH /v0/projects/{id} is called
        Then: Returns 404 not found
        """
        non_existent_id = str(uuid.uuid4())
        payload = {"name": "Updated Name"}

        response = integration_client.patch(
            f"/v0/projects/{non_existent_id}", json=payload
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_patch_project_duplicate_code(
        self, integration_client, app, company_id
    ) -> None:
        """Test updating project with duplicate code.

        Given: Two projects exist with different codes
        When: PATCH /v0/projects/{id} with code of other project
        Then: Returns 409 conflict error
        """
        with app.app_context():
            project1 = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Project 1",
                code="CODE-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            project2 = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Project 2",
                code="CODE-002",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add_all([project1, project2])
            db.session.commit()
            project2_id = str(project2.id)

        payload = {"code": "CODE-001"}  # Try to use project1's code

        response = integration_client.patch(f"/v0/projects/{project2_id}", json=payload)

        assert response.status_code == 409
        data = response.get_json()
        assert "already exists" in data["message"]


class TestProjectDelete:
    """Integration tests for DELETE /v0/projects/{id} endpoint."""

    def test_delete_project_success(self, integration_client, app, company_id) -> None:
        """Test deleting a project without related entities.

        Given: Project exists with no related entities
        When: DELETE /v0/projects/{id} is called
        Then: Returns 204 and removes project from database
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Deletable Project",
                code="DEL-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = integration_client.delete(f"/v0/projects/{project_id}")

        assert response.status_code == 204
        assert response.get_data() == b""

        # Verify deletion from database
        with app.app_context():
            deleted_project = db.session.get(Project, uuid.UUID(project_id))
            assert deleted_project is None

    def test_delete_project_with_tasks_conflict(
        self, integration_client, app, company_id
    ) -> None:
        """Test deleting project with related tasks.

        Given: Project exists with related tasks
        When: DELETE /v0/projects/{id} is called
        Then: Returns 409 conflict error and does not delete
        """
        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Project with Tasks",
                code="DEL-002",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(project)
            db.session.commit()

            task = Task(  # type: ignore[call-arg]
                project_id=project.id,
                name="Child Task",
                type="task",
                status="not_started",
            )
            db.session.add(task)
            db.session.commit()
            project_id = str(project.id)

        response = integration_client.delete(f"/v0/projects/{project_id}")

        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "Conflict"
        assert "Cannot delete project" in data["message"]

        # Verify project still exists
        with app.app_context():
            project_still_exists = db.session.get(Project, uuid.UUID(project_id))
            assert project_still_exists is not None

    def test_delete_project_not_found(self, integration_client) -> None:
        """Test deleting non-existent project.

        Given: Project ID does not exist
        When: DELETE /v0/projects/{id} is called
        Then: Returns 404 not found
        """
        non_existent_id = str(uuid.uuid4())

        response = integration_client.delete(f"/v0/projects/{non_existent_id}")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_delete_project_invalid_uuid(self, integration_client) -> None:
        """Test deleting project with invalid UUID format.

        Given: Invalid UUID string
        When: DELETE /v0/projects/{id} is called
        Then: Returns 404 (invalid UUID treated as not found)
        """
        response = integration_client.delete("/v0/projects/not-a-uuid")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_delete_project_wrong_company(
        self, integration_client, app, generate_uuid
    ) -> None:
        """Test deleting project from different company.

        Given: Project exists for different company
        When: DELETE /v0/projects/{id} is called
        Then: Returns 404 (not accessible)
        """
        other_company_id = generate_uuid()

        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(other_company_id),
                name="Other Company Project",
                code="OTHER-DEL-001",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC) + timedelta(days=30),
            )
            db.session.add(project)
            db.session.commit()
            project_id = str(project.id)

        response = integration_client.delete(f"/v0/projects/{project_id}")

        assert response.status_code == 404

        # Verify project was not deleted
        with app.app_context():
            project_still_exists = db.session.get(Project, uuid.UUID(project_id))
            assert project_still_exists is not None
