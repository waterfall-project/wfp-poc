"""Unit tests for statistics labor by resource endpoint.

This module tests the LaborByResourceResource endpoint for
retrieving labor cost distribution by resource.

Copyright (c) 2025 Waterfall Project. All rights reserved.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.models.assignment import Assignment
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task


class TestLaborByResourceEndpoint:
    """Tests for GET /projects/{project_id}/statistics/labor/by-resource endpoint."""

    @pytest.fixture
    def project(self, app: Flask) -> Project:
        """Create a test project.

        Args:
            app: Flask application instance.

        Returns:
            Created project instance.
        """
        from app import db

        with app.app_context():
            project = Project(
                id=uuid4(),
                name="Test Project",
                company_id=uuid4(),
                start_date=datetime(2024, 11, 1, tzinfo=UTC),
                finish_date=datetime(2026, 12, 31, tzinfo=UTC),
                budget=Decimal("1000000.00"),
            )
            db.session.add(project)
            db.session.commit()
            db.session.refresh(project)
            return project

    @pytest.fixture
    def resources(self, app: Flask, project: Project) -> list[Resource]:
        """Create test resources.

        Args:
            app: Flask application instance.
            project: Test project.

        Returns:
            List of created resource instances.
        """
        from app import db

        with app.app_context():
            resources = [
                Resource(
                    id=uuid4(),
                    company_id=project.company_id,
                    name="Jean Dupont",
                    standard_rate=85.00,
                ),
                Resource(
                    id=uuid4(),
                    company_id=project.company_id,
                    name="Marie Martin",
                    standard_rate=80.00,
                ),
                Resource(
                    id=uuid4(),
                    company_id=project.company_id,
                    name="Pierre Bernard",
                    standard_rate=75.00,
                ),
            ]
            db.session.add_all(resources)
            db.session.commit()
            for res in resources:
                db.session.refresh(res)
            return resources

    @pytest.fixture
    def tasks(self, app: Flask, project: Project) -> list[Task]:
        """Create test tasks.

        Args:
            app: Flask application instance.
            project: Test project.

        Returns:
            List of created task instances.
        """
        from app import db

        with app.app_context():
            tasks = [
                Task(
                    id=uuid4(),
                    project_id=project.id,
                    name="Task 1",
                    wbs_code="1",
                    actual_start_date=datetime(2024, 11, 1, tzinfo=UTC),
                    actual_finish_date=datetime(2024, 11, 30, tzinfo=UTC),
                ),
                Task(
                    id=uuid4(),
                    project_id=project.id,
                    name="Task 2",
                    wbs_code="2",
                    actual_start_date=datetime(2024, 12, 1, tzinfo=UTC),
                    actual_finish_date=datetime(2024, 12, 31, tzinfo=UTC),
                ),
            ]
            db.session.add_all(tasks)
            db.session.commit()
            for task in tasks:
                db.session.refresh(task)
            return tasks

    @pytest.fixture
    def assignments(
        self,
        app: Flask,
        project: Project,
        resources: list[Resource],
        tasks: list[Task],
    ) -> list[Assignment]:
        """Create test assignments.

        Args:
            app: Flask application instance.
            project: Test project.
            resources: Test resources.
            tasks: Test tasks.

        Returns:
            List of created assignment instances.
        """
        from app import db

        with app.app_context():
            assignments = [
                # Jean Dupont - 1000 hours @ 85/hr
                Assignment(
                    id=uuid4(),
                    task_id=tasks[0].id,
                    resource_id=resources[0].id,
                    project_id=project.id,
                    actual_work_minutes=60000,  # 1000 hours
                    actual_cost=Decimal("85000.00"),
                ),
                # Marie Martin - 900 hours @ 80/hr
                Assignment(
                    id=uuid4(),
                    task_id=tasks[0].id,
                    resource_id=resources[1].id,
                    project_id=project.id,
                    actual_work_minutes=54000,  # 900 hours
                    actual_cost=Decimal("72000.00"),
                ),
                # Pierre Bernard - 867 hours @ 75/hr
                Assignment(
                    id=uuid4(),
                    task_id=tasks[1].id,
                    resource_id=resources[2].id,
                    project_id=project.id,
                    actual_work_minutes=52000,  # ~867 hours
                    actual_cost=Decimal("65000.00"),
                ),
            ]
            db.session.add_all(assignments)
            db.session.commit()
            for assignment in assignments:
                db.session.refresh(assignment)
            return assignments

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_success(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        assignments: list[Assignment],
    ) -> None:
        """Test retrieving labor cost by resource.

        Given: Project with assignments to multiple resources
        When: GET /projects/{id}/statistics/labor/by-resource is called
        Then: Status is 200 and breakdown is correct
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/labor/by-resource"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["project_id"] == str(project.id)
        assert data["total_labor_cost"] == 222000.0
        assert data["resource_count"] == 3

        # Verify breakdown (sorted by cost descending)
        breakdown = data["breakdown"]
        assert len(breakdown) == 3

        # Jean Dupont should be first
        assert breakdown[0]["resource_name"] == "Jean Dupont"
        assert breakdown[0]["amount"] == 85000.0
        assert breakdown[0]["percentage"] == pytest.approx(38.29, abs=0.01)
        assert breakdown[0]["hours"] == 1000.0
        assert breakdown[0]["average_rate"] == 85.0

        # Marie Martin second
        assert breakdown[1]["resource_name"] == "Marie Martin"
        assert breakdown[1]["amount"] == 72000.0

        # Verify ECharts format
        assert "echarts_format" in data
        echarts = data["echarts_format"]
        assert echarts["xAxis"]["type"] == "category"
        assert echarts["xAxis"]["data"] == [
            "Jean Dupont",
            "Marie Martin",
            "Pierre Bernard",
        ]
        assert echarts["yAxis"]["type"] == "value"
        assert echarts["series"][0]["name"] == "Labor Cost"
        assert echarts["series"][0]["type"] == "bar"
        assert echarts["series"][0]["data"] == [85000.0, 72000.0, 65000.0]

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_with_limit(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        assignments: list[Assignment],
    ) -> None:
        """Test labor by resource with limit parameter.

        Given: Multiple resources
        When: GET with limit=2 is called
        Then: Only top 2 resources are returned
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/labor/by-resource",
            query_string={"limit": 2},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["resource_count"] == 3
        assert len(data["breakdown"]) == 2

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_invalid_limit(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
    ) -> None:
        """Test labor by resource with invalid limit.

        Given: Valid project
        When: GET with limit > 100 is called
        Then: Status is 400
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/labor/by-resource",
            query_string={"limit": 150},
        )

        assert response.status_code == 400

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_project_not_found(
        self, mock_guardian: MagicMock, authenticated_client: FlaskClient
    ) -> None:
        """Test labor by resource for non-existent project.

        Given: Invalid project ID
        When: GET is called
        Then: Status is 404
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        fake_id = uuid4()
        response = authenticated_client.get(
            f"/v0/projects/{fake_id}/statistics/labor/by-resource"
        )

        assert response.status_code == 404

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_no_assignments(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
    ) -> None:
        """Test labor by resource with no assignments.

        Given: Project with no assignments
        When: GET is called
        Then: Status is 200 with empty breakdown
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/labor/by-resource"
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        assert data["total_labor_cost"] == 0.0
        assert data["resource_count"] == 0
        assert data["breakdown"] == []

    @patch("app.services.guardian_service.requests.post")
    def test_get_labor_by_resource_ascending_order(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
        project: Project,
        assignments: list[Assignment],
    ) -> None:
        """Test labor by resource with ascending sort order.

        Given: Multiple resources
        When: GET with sort_order=asc is called
        Then: Resources are sorted by cost ascending
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_granted": True, "reason": "granted"}
        mock_guardian.return_value = mock_response

        response = authenticated_client.get(
            f"/v0/projects/{project.id}/statistics/labor/by-resource",
            query_string={"sort_order": "asc"},
        )

        assert response.status_code == 200
        data = response.json["data"]  # type: ignore[index]

        breakdown = data["breakdown"]
        # Pierre should be first (lowest cost)
        assert breakdown[0]["resource_name"] == "Pierre Bernard"
        assert breakdown[0]["amount"] == 65000.0
