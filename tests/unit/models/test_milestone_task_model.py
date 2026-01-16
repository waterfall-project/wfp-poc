# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for MilestoneTask model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the MilestoneTask entity.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Milestone, MilestoneTask, Project, Task, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestMilestoneTaskModel:
    """Test suite for MilestoneTask model."""

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
    def milestone(self, app, project):
        """Create a test milestone."""
        milestone = Milestone(
            project_id=project.id,
            name="Test Milestone",
            target_date=DEFAULT_FINISH_DATE,
            budget_weight=Decimal("0.1"),
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone

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

    def test_create_milestone_task(self, app, milestone, task):
        """Test creating a milestone-task link.

        Given: A milestone and a task
        When: Creating a MilestoneTask instance
        Then: Link is created successfully
        """
        milestone_task = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(milestone_task)
        db.session.commit()

        assert milestone_task.id is not None
        assert isinstance(milestone_task.id, uuid.UUID)
        assert milestone_task.milestone_id == milestone.id
        assert milestone_task.task_id == task.id
        assert milestone_task.created_at is not None
        assert milestone_task.updated_at is not None

    def test_milestone_task_unique_constraint(self, app, milestone, task):
        """Test unique constraint on (milestone_id, task_id).

        Given: A milestone-task link exists
        When: Creating another link with the same milestone and task
        Then: IntegrityError is raised
        """
        mt1 = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(mt1)
        db.session.commit()

        mt2 = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(mt2)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

    def test_milestone_task_multiple_tasks_per_milestone(self, app, milestone, project):
        """Test linking multiple tasks to one milestone.

        Given: One milestone and multiple tasks
        When: Creating multiple milestone-task links
        Then: All links are created successfully
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

        mt1 = MilestoneTask(milestone_id=milestone.id, task_id=task1.id)
        mt2 = MilestoneTask(milestone_id=milestone.id, task_id=task2.id)
        db.session.add_all([mt1, mt2])
        db.session.commit()

        assert mt1.milestone_id == milestone.id
        assert mt2.milestone_id == milestone.id
        assert mt1.task_id != mt2.task_id

    def test_milestone_task_multiple_milestones_per_task(self, app, task, project):
        """Test linking one task to multiple milestones.

        Given: One task and multiple milestones
        When: Creating multiple milestone-task links
        Then: All links are created successfully
        """
        milestone1 = Milestone(
            project_id=project.id,
            name="Milestone 1",
            target_date=DEFAULT_FINISH_DATE,
            budget_weight=Decimal("0.1"),
        )
        milestone2 = Milestone(
            project_id=project.id,
            name="Milestone 2",
            target_date=DEFAULT_FINISH_DATE,
            budget_weight=Decimal("0.2"),
        )
        db.session.add_all([milestone1, milestone2])
        db.session.commit()

        mt1 = MilestoneTask(milestone_id=milestone1.id, task_id=task.id)
        mt2 = MilestoneTask(milestone_id=milestone2.id, task_id=task.id)
        db.session.add_all([mt1, mt2])
        db.session.commit()

        assert mt1.task_id == task.id
        assert mt2.task_id == task.id
        assert mt1.milestone_id != mt2.milestone_id

    def test_milestone_task_repr(self, app, milestone, task):
        """Test string representation of MilestoneTask.

        Given: A milestone-task link
        When: Converting to string
        Then: Repr shows milestone_id and task_id
        """
        milestone_task = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(milestone_task)
        db.session.commit()

        repr_str = repr(milestone_task)
        assert "MilestoneTask" in repr_str
        assert str(milestone_task.milestone_id) in repr_str
        assert str(milestone_task.task_id) in repr_str

    def test_milestone_task_relationships_exist(self, app, milestone, task):
        """Test that relationship attributes exist.

        Given: A milestone-task link
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        milestone_task = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(milestone_task)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(milestone_task, "milestone")
        assert hasattr(milestone_task, "task")
        assert milestone_task.milestone == milestone
        assert milestone_task.task == task

    def test_milestone_task_cascade_delete_milestone(self, app, milestone, task):
        """Test cascade delete when milestone is deleted.

        Given: A milestone-task link
        When: Deleting the milestone
        Then: Link is also deleted
        """
        milestone_task = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(milestone_task)
        db.session.commit()

        link_id = milestone_task.id

        # Delete milestone
        db.session.delete(milestone)
        db.session.commit()

        # Verify link was deleted
        deleted_link = db.session.get(MilestoneTask, link_id)
        assert deleted_link is None

    def test_milestone_task_cascade_delete_task(self, app, milestone, task):
        """Test cascade delete when task is deleted.

        Given: A milestone-task link
        When: Deleting the task
        Then: Link is also deleted
        """
        milestone_task = MilestoneTask(
            milestone_id=milestone.id,
            task_id=task.id,
        )
        db.session.add(milestone_task)
        db.session.commit()

        link_id = milestone_task.id

        # Delete task
        db.session.delete(task)
        db.session.commit()

        # Verify link was deleted
        deleted_link = db.session.get(MilestoneTask, link_id)
        assert deleted_link is None
