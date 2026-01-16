# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for Resource CRUD endpoints."""

import uuid
from datetime import UTC, datetime

from app.models.assignment import Assignment
from app.models.db import db
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task


class TestResourceCreate:
    """Integration tests for POST /v0/resources endpoint."""

    def test_create_resource_success(self, integration_client, app, company_id) -> None:
        """Create resource successfully.

        Given: Valid resource data
        When: POST /v0/resources is called
        Then: Returns 201 with persisted resource
        """

        payload = {
            "name": "Integration Engineer",
            "type": "labor",
            "standard_rate": 120.0,
            "overtime_rate": 180.0,
            "email": "eng@example.com",
        }

        response = integration_client.post("/v0/resources", json=payload)

        assert response.status_code == 201
        data = response.get_json()

        assert data["message"] == "Resource created successfully"
        assert data["data"]["name"] == payload["name"]
        assert data["data"]["type"] == "labor"
        assert data["data"]["standard_rate"] == 120.0
        assert data["data"]["overtime_rate"] == 180.0
        assert data["data"]["is_active"] is True

        with app.app_context():
            resource = Resource.query.filter_by(name="Integration Engineer").first()
            assert resource is not None
            assert resource.company_id == uuid.UUID(company_id)

    def test_create_resource_duplicate_name(
        self, integration_client, app, company_id
    ) -> None:
        """Duplicate name returns conflict.

        Given: Resource with same name exists
        When: POST /v0/resources uses duplicate name
        Then: Returns 409 conflict error
        """

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Duplicate Resource",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

        response = integration_client.post(
            "/v0/resources",
            json={"name": "Duplicate Resource", "type": "labor"},
        )

        assert response.status_code == 409
        data = response.get_json()
        assert "already exists" in data["message"]

    def test_create_resource_validation_error(self, integration_client) -> None:
        """Invalid data returns 400.

        Given: Negative rate in payload
        When: POST /v0/resources is called
        Then: Returns 400 validation error
        """

        payload = {"name": "Bad Rate", "standard_rate": -5}

        response = integration_client.post("/v0/resources", json=payload)

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Bad Request"
        assert "standard_rate" in str(data["errors"])

    def test_create_resource_missing_required(self, integration_client) -> None:
        """Missing name returns 400.

        Given: Payload without required name
        When: POST /v0/resources is called
        Then: Returns 400 with validation errors
        """

        response = integration_client.post("/v0/resources", json={"type": "labor"})

        assert response.status_code == 400
        data = response.get_json()
        assert "name" in str(data["errors"])


class TestResourceRetrieve:
    """Integration tests for GET /v0/resources/{id} endpoint."""

    def test_get_resource_success(self, integration_client, app, company_id) -> None:
        """Retrieve resource by ID.

        Given: Resource exists for company
        When: GET /v0/resources/{id} is called
        Then: Returns 200 with resource payload
        """

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Fetch Resource",
                type="material",
                standard_rate=75.0,
                email="fetch@example.com",
            )
            db.session.add(resource)
            db.session.commit()
            db.session.refresh(resource)
            resource_id = str(resource.id)

        response = integration_client.get(f"/v0/resources/{resource_id}")

        assert response.status_code == 200
        data = response.get_json()

        assert data["data"]["id"] == resource_id
        assert data["data"]["name"] == "Fetch Resource"
        assert data["data"]["type"] == "material"
        assert data["data"]["standard_rate"] == 75.0

    def test_get_resource_not_found(self, integration_client) -> None:
        """Non-existent resource returns 404."""

        response = integration_client.get(f"/v0/resources/{uuid.uuid4()}")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Not Found"

    def test_get_resource_invalid_uuid(self, integration_client) -> None:
        """Invalid UUID returns 404."""

        response = integration_client.get("/v0/resources/not-a-uuid")

        assert response.status_code == 404

    def test_get_resource_other_company(
        self, integration_client, app, generate_uuid, company_id
    ) -> None:
        """Resource from other company is hidden.

        Given: Resource belongs to different company
        When: GET /v0/resources/{id} is called
        Then: Returns 404 not found
        """

        other_company = generate_uuid()

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(other_company),
                name="Other Company Resource",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()
            resource_id = str(resource.id)

        response = integration_client.get(f"/v0/resources/{resource_id}")

        assert response.status_code == 404


class TestResourceUpdate:
    """Integration tests for PATCH /v0/resources/{id} endpoint."""

    def test_patch_resource_success(self, integration_client, app, company_id) -> None:
        """Update resource fields successfully."""

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Patch Target",
                type="labor",
                standard_rate=100.0,
                is_active=True,
            )
            db.session.add(resource)
            db.session.commit()
            db.session.refresh(resource)
            resource_id = str(resource.id)

        payload = {"standard_rate": 140.0, "is_active": False}

        response = integration_client.patch(
            f"/v0/resources/{resource_id}", json=payload
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data["message"] == "Resource updated successfully"
        assert data["data"]["standard_rate"] == 140.0
        assert data["data"]["is_active"] is False

        with app.app_context():
            updated = db.session.get(Resource, uuid.UUID(resource_id))
            assert updated is not None
            assert updated.standard_rate is not None
            assert float(updated.standard_rate) == 140.0
            assert updated.is_active is False

    def test_patch_resource_validation_error(
        self, integration_client, app, company_id
    ) -> None:
        """Invalid payload returns 400."""

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Invalid Patch",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()
            resource_id = str(resource.id)

        response = integration_client.patch(
            f"/v0/resources/{resource_id}", json={"standard_rate": -10}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Bad Request"

    def test_patch_resource_missing_payload(
        self, integration_client, app, company_id
    ) -> None:
        """Empty body returns 400."""

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="No Payload",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()
            resource_id = str(resource.id)

        response = integration_client.patch(f"/v0/resources/{resource_id}")

        assert response.status_code == 400
        data = response.get_json()
        assert "At least one field" in data["message"]


class TestResourceDelete:
    """Integration tests for DELETE /v0/resources/{id} endpoint."""

    def test_delete_resource_success(self, integration_client, app, company_id) -> None:
        """Delete resource without assignments."""

        with app.app_context():
            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Delete Me",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()
            resource_id = str(resource.id)

        response = integration_client.delete(f"/v0/resources/{resource_id}")

        assert response.status_code == 204

        with app.app_context():
            deleted = db.session.get(Resource, uuid.UUID(resource_id))
            assert deleted is None

    def test_delete_resource_with_assignments(
        self, integration_client, app, company_id
    ) -> None:
        """Prevent deletion when assignments exist."""

        with app.app_context():
            project = Project(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Project Delete",
                code="RES-DEL",
                start_date=datetime.now(UTC),
                finish_date=datetime.now(UTC),
            )
            db.session.add(project)
            db.session.commit()

            task = Task(  # type: ignore[call-arg]
                project_id=project.id,
                name="Task for assignment",
            )
            db.session.add(task)
            db.session.commit()

            resource = Resource(  # type: ignore[call-arg]
                company_id=uuid.UUID(company_id),
                name="Assigned Resource",
                type="labor",
            )
            db.session.add(resource)
            db.session.commit()

            assignment = Assignment(  # type: ignore[call-arg]
                task_id=task.id,
                resource_id=resource.id,
                project_id=project.id,
            )
            db.session.add(assignment)
            db.session.commit()

            resource_id = str(resource.id)

        response = integration_client.delete(f"/v0/resources/{resource_id}")

        assert response.status_code == 409
        data = response.get_json()
        assert "Cannot delete resource" in data["message"]
