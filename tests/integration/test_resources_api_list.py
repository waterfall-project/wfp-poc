# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for GET /v0/resources endpoint."""

import uuid

import pytest

from app.models.db import db
from app.models.resource import Resource


@pytest.fixture
def integration_resources(app, company_id):
    """Create resources for integration testing."""

    with app.app_context():
        resources: list[Resource] = []
        for i in range(15):
            resource = Resource(
                company_id=uuid.UUID(company_id),
                name=f"Resource {i:02d}",
                type="labor" if i % 2 == 0 else "material",
                standard_rate=50 + i,
                is_active=i % 3 != 0,
            )
            db.session.add(resource)
            resources.append(resource)
        db.session.commit()

        for res in resources:
            db.session.refresh(res)

        return resources


class TestResourceListIntegration:
    """Integration tests for resource listing."""

    def test_list_resources_full_flow(
        self, integration_client, integration_resources
    ) -> None:
        """Paginated list returns resources."""

        response = integration_client.get("/v0/resources?page=1&per_page=10")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 15
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert len(data["data"]) == 10

        first = data["data"][0]
        assert "id" in first
        assert "name" in first
        assert "type" in first
        assert "created_at" in first

    def test_list_resources_filter_by_type(
        self, integration_client, integration_resources
    ) -> None:
        """Filter resources by type."""

        response = integration_client.get("/v0/resources?type=labor")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 8  # half rounded up for even indices
        for res in data["data"]:
            assert res["type"] == "labor"

    def test_list_resources_filter_by_is_active(
        self, integration_client, integration_resources
    ) -> None:
        """Filter resources by active flag."""

        response = integration_client.get("/v0/resources?is_active=true")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] == 10
        for res in data["data"]:
            assert res["is_active"] is True

    def test_list_resources_search(
        self, integration_client, integration_resources
    ) -> None:
        """Search resources by name."""

        response = integration_client.get("/v0/resources?search=Resource 01")

        assert response.status_code == 200
        data = response.get_json()

        assert data["total"] >= 1
        assert any("Resource 01" in r["name"] for r in data["data"])

    def test_list_resources_sort_by_name(
        self, integration_client, integration_resources
    ) -> None:
        """Sort resources by name ascending."""

        response = integration_client.get(
            "/v0/resources?sort_by=name&sort_order=asc&per_page=5"
        )

        assert response.status_code == 200
        data = response.get_json()

        names = [r["name"] for r in data["data"]]
        assert names == sorted(names)

    def test_list_resources_per_page_boundary(
        self, integration_client, integration_resources
    ) -> None:
        """Respect per_page boundary."""

        response = integration_client.get("/v0/resources?per_page=1")

        assert response.status_code == 200
        data = response.get_json()

        assert data["per_page"] == 1
        assert len(data["data"]) == 1
        assert data["total_pages"] == 15
