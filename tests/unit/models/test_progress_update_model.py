# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for ProgressUpdate model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the ProgressUpdate entity.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models import ProgressUpdate, Project, Task, db


class TestProgressUpdateModel:
    """Test suite for ProgressUpdate model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project."""
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project

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

    def test_create_progress_update_minimal_project_level(self, app, project):
        """Test creating a project-level progress update with minimal fields.

        Given: Required fields only (project_id, update_date)
        When: Creating a ProgressUpdate instance
        Then: Update is created with correct defaults
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        assert progress_update.id is not None
        assert isinstance(progress_update.id, uuid.UUID)
        assert progress_update.project_id == project.id
        assert progress_update.task_id is None
        assert progress_update.update_date == date(2026, 6, 1)
        assert progress_update.earned_value is None
        assert progress_update.actual_cost is None
        assert progress_update.notes is None
        assert progress_update.created_at is not None
        assert progress_update.updated_at is not None

    def test_create_progress_update_minimal_task_level(self, app, project, task):
        """Test creating a task-level progress update with minimal fields.

        Given: Required fields (project_id, task_id, update_date)
        When: Creating a ProgressUpdate instance
        Then: Update is created successfully
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        assert progress_update.id is not None
        assert progress_update.project_id == project.id
        assert progress_update.task_id == task.id
        assert progress_update.update_date == date(2026, 6, 1)

    def test_create_progress_update_full(self, app, project, task):
        """Test creating a progress update with all fields populated.

        Given: All fields provided
        When: Creating a ProgressUpdate instance
        Then: Update is created with all values correctly set
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 6, 15),
            earned_value=Decimal("25000.00"),
            actual_cost=Decimal("27000.00"),
            notes="Monthly progress snapshot",
        )
        db.session.add(progress_update)
        db.session.commit()

        assert progress_update.id is not None
        assert progress_update.project_id == project.id
        assert progress_update.task_id == task.id
        assert progress_update.update_date == date(2026, 6, 15)
        assert progress_update.earned_value == Decimal("25000.00")
        assert progress_update.actual_cost == Decimal("27000.00")
        assert progress_update.notes == "Monthly progress snapshot"

    def test_progress_update_multiple_per_project(self, app, project):
        """Test multiple progress updates for same project.

        Given: One project
        When: Creating multiple progress updates for different dates
        Then: All updates are created successfully
        """
        update1 = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 1, 31),
            earned_value=Decimal("10000.00"),
        )
        update2 = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 2, 28),
            earned_value=Decimal("22000.00"),
        )
        db.session.add_all([update1, update2])
        db.session.commit()

        assert update1.project_id == project.id
        assert update2.project_id == project.id
        assert update1.update_date != update2.update_date

    def test_progress_update_multiple_per_task(self, app, project, task):
        """Test multiple progress updates for same task.

        Given: One task
        When: Creating multiple progress updates for different dates
        Then: All updates are created successfully
        """
        update1 = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 1, 15),
            earned_value=Decimal("1000.00"),
        )
        update2 = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 1, 31),
            earned_value=Decimal("2500.00"),
        )
        db.session.add_all([update1, update2])
        db.session.commit()

        assert update1.task_id == task.id
        assert update2.task_id == task.id
        assert update1.update_date != update2.update_date

    def test_progress_update_evm_metrics(self, app, project):
        """Test EVM metrics tracking (EV, AC).

        Given: A progress update
        When: Setting EV and AC values
        Then: Values are tracked correctly
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
            earned_value=Decimal("50000.00"),
            actual_cost=Decimal("55000.00"),
        )
        db.session.add(progress_update)
        db.session.commit()

        assert progress_update.earned_value == Decimal("50000.00")
        assert progress_update.actual_cost == Decimal("55000.00")
        # Cost variance would be: EV - AC = 50000 - 55000 = -5000 (over budget)

    def test_progress_update_cost_precision(self, app, project):
        """Test cost fields with decimal precision.

        Given: A progress update with costs
        When: Setting values with decimals
        Then: Precision is maintained (2 decimal places)
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
            earned_value=Decimal("123456.78"),
            actual_cost=Decimal("123999.99"),
        )
        db.session.add(progress_update)
        db.session.commit()

        assert progress_update.earned_value == Decimal("123456.78")
        assert progress_update.actual_cost == Decimal("123999.99")

    def test_progress_update_with_notes(self, app, project):
        """Test progress update with notes field.

        Given: A progress update with notes
        When: Creating the update
        Then: Notes are stored correctly
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
            notes="Project is ahead of schedule. Team morale is high.",
        )
        db.session.add(progress_update)
        db.session.commit()

        assert (
            progress_update.notes
            == "Project is ahead of schedule. Team morale is high."
        )

    def test_progress_update_repr(self, app, project):
        """Test string representation of ProgressUpdate.

        Given: A progress update instance
        When: Converting to string
        Then: Repr shows id, project_id, and update_date
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        repr_str = repr(progress_update)
        assert "ProgressUpdate" in repr_str
        assert str(progress_update.id) in repr_str

    def test_progress_update_relationships_exist(self, app, project, task):
        """Test that relationship attributes exist.

        Given: A progress update instance with task
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(progress_update, "project")
        assert hasattr(progress_update, "task")
        assert progress_update.project == project
        assert progress_update.task == task

    def test_progress_update_cascade_delete_project(self, app, project):
        """Test cascade delete when project is deleted.

        Given: A progress update linked to a project
        When: Deleting the project
        Then: Progress update is also deleted
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        update_id = progress_update.id

        # Delete project
        db.session.delete(project)
        db.session.commit()

        # Verify progress update was deleted
        deleted_update = db.session.get(ProgressUpdate, update_id)
        assert deleted_update is None

    def test_progress_update_cascade_delete_task(self, app, project, task):
        """Test CASCADE delete when task is deleted.

        Given: A task-level progress update
        When: Deleting the task
        Then: Update is also deleted (CASCADE)
        """
        progress_update = ProgressUpdate(
            project_id=project.id,
            task_id=task.id,
            update_date=date(2026, 6, 1),
        )
        db.session.add(progress_update)
        db.session.commit()

        update_id = progress_update.id

        # Delete task - should CASCADE delete the progress update
        db.session.delete(task)
        db.session.commit()

        # Verify update was deleted
        deleted_update = db.session.get(ProgressUpdate, update_id)
        assert deleted_update is None
