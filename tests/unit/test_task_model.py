# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Task model.

Tests cover model creation, validation, constraints, relationships,
hierarchies, and business logic for the Task entity.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Project, Task, db


class TestTaskModel:
    """Test suite for Task model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project.

        Returns a committed Project instance for use in task tests.
        """
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
        )
        db.session.add(project)
        db.session.commit()
        # Refresh to ensure all attributes are loaded
        db.session.refresh(project)
        return project

    def test_create_task_minimal(self, app, project):
        """Test creating a task with minimal required fields.

        Given: Required fields only (project_id, name, type, status)
        When: Creating a Task instance
        Then: Task is created with correct defaults
        """
        task = Task(
            project_id=project.id,
            name="Test Task",
            type="task",
            status="not_started",
        )
        db.session.add(task)
        db.session.commit()

        assert task.id is not None
        assert isinstance(task.id, uuid.UUID)
        assert task.project_id == project.id
        assert task.name == "Test Task"
        assert task.type == "task"
        assert task.status == "not_started"
        assert task.percent_complete == 0.0
        assert task.is_critical is False
        assert task.parent_id is None
        assert task.ms_project_uid is None

    def test_create_task_full(self, app, project):
        """Test creating a task with all fields populated.

        Given: All fields provided
        When: Creating a Task instance
        Then: Task is created with all values correctly set
        """
        task = Task(
            project_id=project.id,
            name="Full Test Task",
            type="task",
            status="in_progress",
            ms_project_uid=456,
            wbs_code="1.2.3",
            description="Detailed task description",
            planned_start_date=date(2026, 1, 15),
            planned_finish_date=date(2026, 1, 30),
            planned_duration_minutes=9600,  # 160 hours
            actual_start_date=date(2026, 1, 16),
            percent_complete=45.50,
            planned_cost=5000.00,
            earned_value=2275.00,
            actual_cost=2500.00,
            remaining_cost=2500.00,
            is_critical=True,
        )
        db.session.add(task)
        db.session.commit()

        assert task.ms_project_uid == 456
        assert task.wbs_code == "1.2.3"
        assert task.description == "Detailed task description"
        assert task.planned_start_date == date(2026, 1, 15)
        assert task.planned_finish_date == date(2026, 1, 30)
        assert task.planned_duration_minutes == 9600
        assert task.actual_start_date == date(2026, 1, 16)
        assert task.percent_complete == 45.50
        assert float(task.planned_cost) == 5000.00
        assert float(task.earned_value) == 2275.00
        assert float(task.actual_cost) == 2500.00
        assert float(task.remaining_cost) == 2500.00
        assert task.is_critical is True

    def test_task_hierarchical_structure(self, app, project):
        """Test parent-child task relationships.

        Given: A parent task
        When: Creating child tasks with parent_id
        Then: Hierarchical structure is created correctly
        """
        # Create parent task
        parent = Task(
            project_id=project.id,
            name="Parent Task",
            type="summary",
            status="not_started",
        )
        db.session.add(parent)
        db.session.commit()

        # Create child tasks
        child1 = Task(
            project_id=project.id,
            parent_id=parent.id,
            name="Child Task 1",
            type="task",
            status="not_started",
        )
        child2 = Task(
            project_id=project.id,
            parent_id=parent.id,
            name="Child Task 2",
            type="task",
            status="not_started",
        )
        db.session.add_all([child1, child2])
        db.session.commit()

        # Verify relationships
        assert len(parent.children) == 2
        assert child1 in parent.children
        assert child2 in parent.children
        assert child1.parent == parent
        assert child2.parent == parent

    def test_task_unique_ms_project_uid_per_project(self, app, project):
        """Test unique constraint on (project_id, ms_project_uid).

        Given: A task with a specific ms_project_uid exists for a project
        When: Creating another task with the same ms_project_uid for the same project
        Then: IntegrityError is raised
        """
        task1 = Task(
            project_id=project.id,
            name="Task 1",
            type="task",
            status="not_started",
            ms_project_uid=100,
        )
        db.session.add(task1)
        db.session.commit()

        task2 = Task(
            project_id=project.id,
            name="Task 2",
            type="task",
            status="not_started",
            ms_project_uid=100,
        )
        db.session.add(task2)

        with pytest.raises(IntegrityError):
            db.session.commit()

        # Rollback to clean session state after IntegrityError
        db.session.rollback()

    def test_task_type_values(self, app, project):
        """Test valid type values.

        Given: Valid type values (task, summary, milestone)
        When: Creating tasks with each type
        Then: Tasks are created successfully
        """
        types = ["task", "summary", "milestone"]

        for task_type in types:
            task = Task(
                project_id=project.id,
                name=f"Task {task_type}",
                type=task_type,
                status="not_started",
            )
            db.session.add(task)
            db.session.commit()

            assert task.type == task_type
            db.session.rollback()

    def test_task_status_values(self, app, project):
        """Test valid status values.

        Given: Valid status values (not_started, in_progress, completed, cancelled)
        When: Creating tasks with each status
        Then: Tasks are created successfully
        """
        statuses = ["not_started", "in_progress", "completed", "cancelled"]

        for status in statuses:
            task = Task(
                project_id=project.id,
                name=f"Task {status}",
                type="task",
                status=status,
            )
            db.session.add(task)
            db.session.commit()

            assert task.status == status
            db.session.rollback()

    def test_task_percent_complete_range(self, app, project):
        """Test percent_complete within valid range (0-100).

        Given: Valid percent_complete values
        When: Creating tasks with 0, 50, and 100 percent complete
        Then: Tasks are created successfully
        """
        values = [0.0, 50.0, 100.0]

        for value in values:
            task = Task(
                project_id=project.id,
                name=f"Task {value}%",
                type="task",
                status="in_progress",
                percent_complete=value,
            )
            db.session.add(task)
            db.session.commit()

            assert task.percent_complete == value
            db.session.rollback()

    def test_task_critical_path_flag(self, app, project):
        """Test critical path flag.

        Given: Tasks with different is_critical values
        When: Creating and querying tasks
        Then: Critical tasks can be identified
        """
        critical_task = Task(
            project_id=project.id,
            name="Critical Task",
            type="task",
            status="not_started",
            is_critical=True,
        )
        normal_task = Task(
            project_id=project.id,
            name="Normal Task",
            type="task",
            status="not_started",
            is_critical=False,
        )
        db.session.add_all([critical_task, normal_task])
        db.session.commit()

        assert critical_task.is_critical is True
        assert normal_task.is_critical is False

    def test_task_repr(self, app, project):
        """Test string representation of Task.

        Given: A task instance
        When: Converting to string
        Then: Repr shows id, name, and status
        """
        task = Task(
            project_id=project.id,
            name="Test Task",
            type="task",
            status="in_progress",
        )
        db.session.add(task)
        db.session.commit()

        repr_str = repr(task)
        assert "Task" in repr_str
        assert str(task.id) in repr_str
        assert "Test Task" in repr_str
        assert "in_progress" in repr_str

    def test_task_relationships_exist(self, app, project):
        """Test that relationship attributes exist.

        Given: A task instance
        When: Accessing relationship attributes
        Then: Attributes exist and return empty lists
        """
        task = Task(
            project_id=project.id,
            name="Test Task",
            type="task",
            status="not_started",
        )
        db.session.add(task)
        db.session.commit()

        # Test relationships exist
        assert hasattr(task, "project")
        assert hasattr(task, "parent")
        assert hasattr(task, "children")
        assert hasattr(task, "predecessors")
        assert hasattr(task, "successors")
        assert hasattr(task, "assignments")
        assert hasattr(task, "milestone_links")
        assert hasattr(task, "progress_updates")
        assert hasattr(task, "rae_entries")

        # Test collections are initially empty
        assert task.children == []
        assert task.predecessors == []
        assert task.successors == []
        assert task.assignments == []
        assert task.milestone_links == []
        assert task.progress_updates == []
        assert task.rae_entries == []

    def test_task_cascade_delete_children(self, app, project):
        """Test cascade delete of child tasks.

        Given: A parent task with children
        When: Deleting the parent task
        Then: Child tasks are also deleted
        """
        parent = Task(
            project_id=project.id,
            name="Parent Task",
            type="summary",
            status="not_started",
        )
        db.session.add(parent)
        db.session.commit()

        child = Task(
            project_id=project.id,
            parent_id=parent.id,
            name="Child Task",
            type="task",
            status="not_started",
        )
        db.session.add(child)
        db.session.commit()

        child_id = child.id

        # Delete parent
        db.session.delete(parent)
        db.session.commit()

        # Child should also be deleted
        assert db.session.get(Task, child_id) is None
