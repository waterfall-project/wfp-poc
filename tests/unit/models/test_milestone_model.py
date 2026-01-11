# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Milestone model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the Milestone entity.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Milestone, Project, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestMilestoneModel:
    """Test suite for Milestone model."""

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

    def test_create_milestone_minimal(self, app, project):
        """Test creating a milestone with minimal required fields.

        Given: Required fields only (project_id, name)
        When: Creating a Milestone instance
        Then: Milestone is created with correct defaults
        """
        milestone = Milestone(
            project_id=project.id,
            name="Test Milestone",
        )
        db.session.add(milestone)
        db.session.commit()

        assert milestone.id is not None
        assert isinstance(milestone.id, uuid.UUID)
        assert milestone.project_id == project.id
        assert milestone.name == "Test Milestone"
        assert milestone.status == "not_reached"  # Default value
        assert milestone.ms_project_uid is None
        assert milestone.description is None
        assert milestone.planned_date is None
        assert milestone.actual_date is None
        assert milestone.created_at is not None
        assert milestone.updated_at is not None

    def test_create_milestone_full(self, app, project):
        """Test creating a milestone with all fields populated.

        Given: All fields provided
        When: Creating a Milestone instance
        Then: Milestone is created with all values correctly set
        """
        milestone = Milestone(
            project_id=project.id,
            ms_project_uid=100,
            name="Full Test Milestone",
            description="A comprehensive milestone description",
            planned_date=date(2026, 6, 30),
            actual_date=date(2026, 7, 5),
            status="reached",
        )
        db.session.add(milestone)
        db.session.commit()

        assert milestone.id is not None
        assert milestone.project_id == project.id
        assert milestone.ms_project_uid == 100
        assert milestone.name == "Full Test Milestone"
        assert milestone.description == "A comprehensive milestone description"
        assert milestone.planned_date == date(2026, 6, 30)
        assert milestone.actual_date == date(2026, 7, 5)
        assert milestone.status == "reached"

    def test_milestone_status_values(self, app, project):
        """Test valid status values.

        Given: Valid status values (not_reached, reached, missed)
        When: Creating milestones with each status
        Then: Milestones are created successfully
        """
        statuses = ["not_reached", "reached", "missed"]

        for status in statuses:
            milestone = Milestone(
                project_id=project.id,
                name=f"Milestone {status}",
                status=status,
            )
            db.session.add(milestone)
            db.session.commit()

            assert milestone.status == status

    def test_milestone_unique_ms_project_uid_per_project(
        self, app, project, generate_uuid
    ):
        """Test unique constraint on (project_id, ms_project_uid).

        Given: A milestone with a specific ms_project_uid exists for a project
        When: Creating another milestone with the same ms_project_uid for the same project
        Then: IntegrityError is raised
        """
        milestone1 = Milestone(
            project_id=project.id,
            name="Milestone 1",
            ms_project_uid=100,
        )
        db.session.add(milestone1)
        db.session.commit()

        milestone2 = Milestone(
            project_id=project.id,
            name="Milestone 2",
            ms_project_uid=100,
        )
        db.session.add(milestone2)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

    def test_milestone_same_ms_project_uid_different_projects(
        self, app, company_id, generate_uuid
    ):
        """Test same ms_project_uid allowed for different projects.

        Given: Two different projects
        When: Creating milestones with the same ms_project_uid for each project
        Then: Both milestones are created successfully
        """
        project1 = Project(
            company_id=uuid.UUID(company_id),
            name="Project 1",
            start_date=DEFAULT_START_DATE,
            finish_date=DEFAULT_FINISH_DATE,
        )
        project2 = Project(
            company_id=uuid.UUID(company_id),
            name="Project 2",
            start_date=DEFAULT_START_DATE + (DEFAULT_FINISH_DATE - DEFAULT_START_DATE),
            finish_date=DEFAULT_FINISH_DATE
            + (DEFAULT_FINISH_DATE - DEFAULT_START_DATE),
        )
        db.session.add_all([project1, project2])
        db.session.commit()

        milestone1 = Milestone(
            project_id=project1.id,
            name="Milestone 1",
            ms_project_uid=100,
        )
        milestone2 = Milestone(
            project_id=project2.id,
            name="Milestone 2",
            ms_project_uid=100,
        )
        db.session.add_all([milestone1, milestone2])
        db.session.commit()

        assert milestone1.ms_project_uid == milestone2.ms_project_uid
        assert milestone1.project_id != milestone2.project_id

    def test_milestone_planned_vs_actual_date(self, app, project):
        """Test planned vs actual date tracking.

        Given: A milestone with planned date
        When: Setting actual date
        Then: Both dates are tracked independently
        """
        milestone = Milestone(
            project_id=project.id,
            name="Date Milestone",
            planned_date=date(2026, 6, 1),
        )
        db.session.add(milestone)
        db.session.commit()

        assert milestone.planned_date == date(2026, 6, 1)
        assert milestone.actual_date is None

        # Update actual date
        milestone.actual_date = date(2026, 6, 5)
        db.session.commit()

        assert milestone.actual_date == date(2026, 6, 5)
        assert milestone.planned_date == date(2026, 6, 1)

    def test_milestone_repr(self, app, project):
        """Test string representation of Milestone.

        Given: A milestone instance
        When: Converting to string
        Then: Repr shows id, name, and status
        """
        milestone = Milestone(
            project_id=project.id,
            name="Test Milestone",
            status="reached",
        )
        db.session.add(milestone)
        db.session.commit()

        repr_str = repr(milestone)
        assert "Milestone" in repr_str
        assert str(milestone.id) in repr_str
        assert milestone.name in repr_str
        assert milestone.status in repr_str

    def test_milestone_relationships_exist(self, app, project):
        """Test that relationship attributes exist.

        Given: A milestone instance
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        milestone = Milestone(
            project_id=project.id,
            name="Test Milestone",
        )
        db.session.add(milestone)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(milestone, "project")
        assert hasattr(milestone, "task_links")
        assert milestone.project == project
        assert isinstance(milestone.task_links, list)
        assert len(milestone.task_links) == 0  # No task links created yet

    def test_milestone_cascade_delete(self, app, project):
        """Test cascade delete when project is deleted.

        Given: A milestone linked to a project
        When: Deleting the project
        Then: Milestone is also deleted
        """
        milestone = Milestone(
            project_id=project.id,
            name="Test Milestone",
        )
        db.session.add(milestone)
        db.session.commit()

        milestone_id = milestone.id

        # Delete project
        db.session.delete(project)
        db.session.commit()

        # Verify milestone was deleted
        deleted_milestone = db.session.get(Milestone, milestone_id)
        assert deleted_milestone is None

    def test_milestone_null_ms_project_uid_allowed(self, app, project):
        """Test that ms_project_uid can be null.

        Given: No ms_project_uid provided
        When: Creating multiple milestones without ms_project_uid
        Then: All milestones are created successfully
        """
        milestone1 = Milestone(
            project_id=project.id,
            name="Milestone Without UID 1",
        )
        milestone2 = Milestone(
            project_id=project.id,
            name="Milestone Without UID 2",
        )

        db.session.add_all([milestone1, milestone2])
        db.session.commit()

        assert milestone1.ms_project_uid is None
        assert milestone2.ms_project_uid is None
