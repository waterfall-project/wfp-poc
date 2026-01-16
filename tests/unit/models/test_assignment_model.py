# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Assignment model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the Assignment entity.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Assignment, Project, Resource, Task, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestAssignmentModel:
    """Test suite for Assignment model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project."""
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
            start_date=DEFAULT_START_DATE,
            finish_date=DEFAULT_FINISH_DATE,
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project

    @pytest.fixture
    def resource(self, app, company_id):
        """Create a test resource."""
        resource = Resource(
            company_id=uuid.UUID(company_id),
            name="Test Resource",
            type="labor",
        )
        db.session.add(resource)
        db.session.commit()
        db.session.refresh(resource)
        return resource

    @pytest.fixture
    def task(self, app, project):
        """Create a test task."""
        task = Task(
            project_id=project.id,
            name="Test Task",
            type="task",
            status="not_started",
        )
        db.session.add(task)
        db.session.commit()
        db.session.refresh(task)
        return task

    def test_create_assignment_minimal(self, app, project, resource, task):
        """Test creating an assignment with minimal required fields.

        Given: Required fields only (task_id, resource_id, project_id)
        When: Creating an Assignment instance
        Then: Assignment is created with correct defaults
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.id is not None
        assert isinstance(assignment.id, uuid.UUID)
        assert assignment.task_id == task.id
        assert assignment.resource_id == resource.id
        assert assignment.project_id == project.id
        assert assignment.planned_work_minutes is None
        assert assignment.actual_work_minutes is None
        assert assignment.planned_cost is None
        assert assignment.actual_cost == Decimal("0.00")
        assert assignment.created_at is not None
        assert assignment.updated_at is not None

    def test_create_assignment_full(self, app, project, resource, task):
        """Test creating an assignment with all fields populated.

        Given: All fields provided
        When: Creating an Assignment instance
        Then: Assignment is created with all values correctly set
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
            planned_work_minutes=480,  # 8 hours
            actual_work_minutes=450,  # 7.5 hours
            planned_cost=Decimal("800.00"),
            actual_cost=Decimal("750.00"),
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.id is not None
        assert assignment.planned_work_minutes == 480
        assert assignment.actual_work_minutes == 450
        assert assignment.planned_cost == Decimal("800.00")
        assert assignment.actual_cost == Decimal("750.00")

    def test_assignment_unique_constraint(self, app, project, resource, task):
        """Test unique constraint on (task_id, resource_id).

        Given: An assignment exists for a task-resource pair
        When: Creating another assignment for the same pair
        Then: IntegrityError is raised
        """
        assignment1 = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment1)
        db.session.commit()

        assignment2 = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment2)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

    def test_assignment_same_resource_different_tasks(self, app, project, resource):
        """Test assigning same resource to different tasks.

        Given: One resource and multiple tasks
        When: Creating assignments for different tasks
        Then: All assignments are created successfully
        """
        task1 = Task(
            project_id=project.id,
            name="Task 1",
            type="task",
            status="not_started",
        )
        task2 = Task(
            project_id=project.id,
            name="Task 2",
            type="task",
            status="not_started",
        )
        db.session.add_all([task1, task2])
        db.session.commit()

        assignment1 = Assignment(
            task_id=task1.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        assignment2 = Assignment(
            task_id=task2.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add_all([assignment1, assignment2])
        db.session.commit()

        assert assignment1.resource_id == resource.id
        assert assignment2.resource_id == resource.id
        assert assignment1.task_id != assignment2.task_id

    def test_assignment_same_task_different_resources(
        self, app, project, task, company_id
    ):
        """Test assigning different resources to same task.

        Given: One task and multiple resources
        When: Creating assignments for different resources
        Then: All assignments are created successfully
        """
        resource1 = Resource(
            company_id=uuid.UUID(company_id),
            name="Resource 1",
            type="labor",
        )
        resource2 = Resource(
            company_id=uuid.UUID(company_id),
            name="Resource 2",
            type="labor",
        )
        db.session.add_all([resource1, resource2])
        db.session.commit()

        assignment1 = Assignment(
            task_id=task.id,
            resource_id=resource1.id,
            project_id=project.id,
        )
        assignment2 = Assignment(
            task_id=task.id,
            resource_id=resource2.id,
            project_id=project.id,
        )
        db.session.add_all([assignment1, assignment2])
        db.session.commit()

        assert assignment1.task_id == task.id
        assert assignment2.task_id == task.id
        assert assignment1.resource_id != assignment2.resource_id

    def test_assignment_work_minutes_tracking(self, app, project, resource, task):
        """Test work minutes tracking (planned vs actual).

        Given: An assignment with planned work
        When: Updating actual work
        Then: Both planned and actual are tracked independently
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
            planned_work_minutes=480,  # 8 hours
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.planned_work_minutes == 480
        assert assignment.actual_work_minutes is None

        # Update actual work
        assignment.actual_work_minutes = 510  # 8.5 hours
        db.session.commit()

        assert assignment.actual_work_minutes == 510
        assert assignment.planned_work_minutes == 480

    def test_assignment_cost_precision(self, app, project, resource, task):
        """Test cost fields with decimal precision.

        Given: An assignment with costs
        When: Setting cost values with decimals
        Then: Precision is maintained (2 decimal places)
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
            planned_cost=Decimal("1234.56"),
            actual_cost=Decimal("1250.75"),
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.planned_cost == Decimal("1234.56")
        assert assignment.actual_cost == Decimal("1250.75")

    def test_assignment_repr(self, app, project, resource, task):
        """Test string representation of Assignment.

        Given: An assignment instance
        When: Converting to string
        Then: Repr shows id, task_id, and resource_id
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment)
        db.session.commit()

        repr_str = repr(assignment)
        assert "Assignment" in repr_str
        assert str(assignment.id) in repr_str

    def test_assignment_relationships_exist(self, app, project, resource, task):
        """Test that relationship attributes exist.

        Given: An assignment instance
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(assignment, "task")
        assert hasattr(assignment, "resource")
        assert hasattr(assignment, "project")
        assert assignment.task == task
        assert assignment.resource == resource
        assert assignment.project == project

    def test_assignment_cascade_delete_task(self, app, project, resource, task):
        """Test cascade delete when task is deleted.

        Given: An assignment
        When: Deleting the task
        Then: Assignment is also deleted
        """
        assignment = Assignment(
            task_id=task.id,
            resource_id=resource.id,
            project_id=project.id,
        )
        db.session.add(assignment)
        db.session.commit()

        assignment_id = assignment.id

        # Delete task
        db.session.delete(task)
        db.session.commit()

        # Verify assignment was deleted
        deleted_assignment = db.session.get(Assignment, assignment_id)
        assert deleted_assignment is None
