# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Assignment resources."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from app.models.assignment import Assignment
from app.models.db import db
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask import Flask
    from flask.testing import FlaskClient


def _create_project(company_id: str) -> Project:
    start_date = datetime(2024, 1, 1, 9, 0)
    finish_date = start_date + timedelta(days=30)
    project = Project(
        company_id=uuid.UUID(company_id),
        name="Test Project",
        code="TP-001",
        start_date=start_date,
        finish_date=finish_date,
        status="active",
    )
    db.session.add(project)
    db.session.commit()
    db.session.refresh(project)
    return project


def _create_task(project: Project) -> Task:
    task = Task(
        project_id=project.id,
        name="Task A",
        status="not_started",
    )
    db.session.add(task)
    db.session.commit()
    db.session.refresh(task)
    return task


def _create_resource(company_id: str) -> Resource:
    resource = Resource(
        company_id=uuid.UUID(company_id),
        name="Resource A",
        type="labor",
        email="res@example.com",
    )
    db.session.add(resource)
    db.session.commit()
    db.session.refresh(resource)
    return resource


def _create_assignment(project: Project, task: Task, resource: Resource) -> Assignment:
    assignment = Assignment(
        project_id=project.id,
        task_id=task.id,
        resource_id=resource.id,
        percent_allocation=100,
        planned_work_minutes=2400,
        planned_cost=Decimal("3400.00"),
        actual_cost=Decimal("0.00"),
    )
    db.session.add(assignment)
    db.session.commit()
    db.session.refresh(assignment)
    return assignment


class TestAssignmentCreate:
    """Tests for POST /v0/projects/{project_id}/assignments."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_assignment_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given valid payload, when creating assignment then returns 201."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)

        payload = {
            "task_id": str(task.id),
            "resource_id": str(resource.id),
            "work_hours": "PT40H0M0S",
            "percent_allocation": 100,
            "cost": "3400.00",
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/assignments", json=payload
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["data"]["task_id"] == str(task.id)
        assert body["data"]["resource_id"] == str(resource.id)
        assert body["data"]["work_hours"] == "PT40H0M0S"
        assert body["data"]["percent_allocation"] == 100

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_assignment_duplicate_returns_conflict(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given duplicate task/resource, when creating then returns 409."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            _create_assignment(project, task, resource)

        payload = {
            "task_id": str(task.id),
            "resource_id": str(resource.id),
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/assignments", json=payload
        )

        assert response.status_code == 409
        body = response.get_json()
        assert "correlation_id" in body
        assert "Assignment already exists" in body["message"]
        assert "X-Correlation-ID" in response.headers

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_assignment_rejects_seconds_in_duration(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given work_hours with seconds, when creating then returns 400."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)

        payload = {
            "task_id": str(task.id),
            "resource_id": str(resource.id),
            "work_hours": "PT1H0M30S",
        }

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/assignments", json=payload
        )

        assert response.status_code == 400
        body = response.get_json()
        assert "Seconds must be 0" in body["message"] or "errors" in body

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_create_assignment_cross_company_returns_unprocessable(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
        generate_uuid: Callable[[], str],
    ) -> None:
        """Given resource from other company, returns 422."""
        mock_guardian.return_value = (True, "granted")
        other_company = generate_uuid()
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(other_company)

        payload = {"task_id": str(task.id), "resource_id": str(resource.id)}

        response = authenticated_client.post(
            f"/v0/projects/{project.id}/assignments", json=payload
        )

        assert response.status_code == 422
        body = response.get_json()
        assert body["message"] == "Resource and task must belong to the same company"


class TestAssignmentList:
    """Tests for GET /v0/projects/{project_id}/assignments."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_list_assignments_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given assignments exist, when listing then returns paginated data."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            _create_assignment(project, task, resource)

        response = authenticated_client.get(f"/v0/projects/{project.id}/assignments")

        assert response.status_code == 200
        body = response.get_json()
        assert body["data"][0]["task_id"] == str(task.id)
        assert body["page"] == 1
        assert body["per_page"] == 20


class TestAssignmentGet:
    """Tests for GET /v0/projects/{project_id}/assignments/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_get_assignment_not_found(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Given unknown assignment, when get then returns 404."""
        mock_guardian.return_value = (True, "granted")

        response = authenticated_client.get(
            "/v0/projects/00000000-0000-0000-0000-000000000000/assignments/00000000-0000-0000-0000-000000000000"
        )

        assert response.status_code == 404

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_get_assignment_invalid_uuid_returns_bad_request(
        self,
        mock_guardian: MagicMock,
        authenticated_client: FlaskClient,
    ) -> None:
        """Given invalid UUID in path, when get then returns 400."""
        mock_guardian.return_value = (True, "granted")

        response = authenticated_client.get(
            "/v0/projects/not-a-uuid/assignments/also-bad"
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Bad Request"


class TestAssignmentPatch:
    """Tests for PATCH /v0/projects/{project_id}/assignments/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_update_assignment_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given valid payload, when patch then updates assignment."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            assignment = _create_assignment(project, task, resource)

        payload = {
            "work_hours": "PT10H0M0S",
            "percent_allocation": 75,
            "actual_work": "PT8H0M0S",
            "actual_cost": "1200.00",
        }

        response = authenticated_client.patch(
            f"/v0/projects/{project.id}/assignments/{assignment.id}", json=payload
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["data"]["percent_allocation"] == 75
        assert body["data"]["work_hours"] == "PT10H0M0S"
        assert body["data"]["actual_work"] == "PT8H0M0S"


class TestAssignmentDelete:
    """Tests for DELETE /v0/projects/{project_id}/assignments/{id}."""

    @patch("app.utils.jwt_decorators.GuardianService.check_access")
    def test_delete_assignment_success(
        self,
        mock_guardian: MagicMock,
        app: Flask,
        authenticated_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Given existing assignment, when delete then returns 204."""
        mock_guardian.return_value = (True, "granted")
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            assignment = _create_assignment(project, task, resource)

        response = authenticated_client.delete(
            f"/v0/projects/{project.id}/assignments/{assignment.id}"
        )

        assert response.status_code == 204
        with app.app_context():
            assert db.session.get(Assignment, assignment.id) is None
