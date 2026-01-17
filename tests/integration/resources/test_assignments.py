# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Integration tests for Assignment API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from app.models.assignment import Assignment
from app.models.db import db
from app.models.project import Project
from app.models.resource import Resource
from app.models.task import Task

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


def _create_project(company_id: str) -> Project:
    """Create a project for integration tests."""
    start_date = datetime(2024, 1, 1, 9, 0)
    finish_date = start_date + timedelta(days=30)
    project = Project(
        company_id=uuid.UUID(company_id),
        name="Integration Project",
        code="INT-001",
        start_date=start_date,
        finish_date=finish_date,
        status="active",
    )  # type: ignore[call-arg]
    db.session.add(project)
    db.session.commit()
    db.session.refresh(project)
    return project


def _create_task(project: Project) -> Task:
    """Create a task bound to a project."""
    task = Task(project_id=project.id, name="Integration Task", status="not_started")  # type: ignore[call-arg]
    db.session.add(task)
    db.session.commit()
    db.session.refresh(task)
    return task


def _create_resource(company_id: str) -> Resource:
    """Create a resource for assignments."""
    resource = Resource(
        company_id=uuid.UUID(company_id),
        name="Integration Resource",
        type="labor",
        email="int@example.com",
    )
    db.session.add(resource)
    db.session.commit()
    db.session.refresh(resource)
    return resource


def _create_assignment(project: Project, task: Task, resource: Resource) -> Assignment:
    """Create an assignment linking project, task, and resource."""
    assignment = Assignment(
        project_id=project.id,
        task_id=task.id,
        resource_id=resource.id,
        percent_allocation=100,
        planned_work_minutes=2400,
        planned_cost=Decimal("1000.00"),
        actual_cost=Decimal("0.00"),
    )
    db.session.add(assignment)
    db.session.commit()
    db.session.refresh(assignment)
    return assignment


class TestAssignmentsAPI:
    """Integration coverage for assignments CRUD."""

    @pytest.fixture(autouse=True)
    def setup_data(self, app: Flask, company_id: str):
        """Reset assignment-related tables between tests."""
        with app.app_context():
            yield
            db.session.query(Assignment).delete()
            db.session.query(Task).delete()
            db.session.query(Resource).delete()
            db.session.query(Project).delete()
            db.session.commit()

    def test_create_assignment_success(
        self,
        app: Flask,
        integration_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test creating an assignment.

        Given: A project, task, and resource exist for the same company
        When: POST /v0/projects/{project_id}/assignments is called with valid payload
        Then: Assignment is created with 201 and returned payload matches inputs
        """
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)

        payload = {
            "task_id": str(task.id),
            "resource_id": str(resource.id),
            "work_hours": "PT40H0M0S",
            "cost": "1500.00",
        }

        response = integration_client.post(
            f"/v0/projects/{project.id}/assignments", json=payload
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["data"]["task_id"] == str(task.id)
        assert body["data"]["resource_id"] == str(resource.id)
        assert body["data"]["work_hours"] == "PT40H0M0S"

    def test_list_assignments_with_filters(
        self,
        app: Flask,
        integration_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test listing assignments with filter.

        Given: A project with one assignment exists
        When: GET /v0/projects/{project_id}/assignments filtered by task_id
        Then: Returns 200 with a single assignment matching the filter
        """
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            _create_assignment(project, task, resource)

        response = integration_client.get(
            f"/v0/projects/{project.id}/assignments?task_id={task.id}"
        )

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["data"]) == 1
        assert body["data"][0]["task_id"] == str(task.id)

    def test_get_assignment_success(
        self,
        app: Flask,
        integration_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test retrieving an assignment.

        Given: An assignment exists
        When: GET /v0/projects/{project_id}/assignments/{assignment_id} is called
        Then: Returns 200 with assignment data
        """
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            assignment = _create_assignment(project, task, resource)

        response = integration_client.get(
            f"/v0/projects/{project.id}/assignments/{assignment.id}"
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["data"]["id"] == str(assignment.id)

    def test_patch_assignment_updates_fields(
        self,
        app: Flask,
        integration_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test partially updating an assignment.

        Given: An assignment exists
        When: PATCH /v0/projects/{project_id}/assignments/{assignment_id} updates fields
        Then: Returns 200 with updated percent_allocation and actual work/cost
        """
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            assignment = _create_assignment(project, task, resource)

        payload = {
            "percent_allocation": 80,
            "actual_work": "PT5H0M0S",
            "actual_cost": "500.00",
        }

        response = integration_client.patch(
            f"/v0/projects/{project.id}/assignments/{assignment.id}", json=payload
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["data"]["percent_allocation"] == 80
        assert body["data"]["actual_work"] == "PT5H0M0S"
        assert body["data"]["actual_cost"] == 500.0

    def test_delete_assignment_success(
        self,
        app: Flask,
        integration_client: FlaskClient,
        company_id: str,
    ) -> None:
        """Test deleting an assignment.

        Given: An assignment exists
        When: DELETE /v0/projects/{project_id}/assignments/{assignment_id} is called
        Then: Returns 204 and assignment is removed from the database
        """
        with app.app_context():
            project = _create_project(company_id)
            task = _create_task(project)
            resource = _create_resource(company_id)
            assignment = _create_assignment(project, task, resource)

        response = integration_client.delete(
            f"/v0/projects/{project.id}/assignments/{assignment.id}"
        )

        assert response.status_code == 204
        assert response.data == b""
        with app.app_context():
            assert db.session.get(Assignment, assignment.id) is None
