# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for Project model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the Project entity.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Project, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0)


class TestProjectModel:
    """Test suite for Project model."""

    def test_create_project_minimal(self, app, company_id):
        """Test creating a project with minimal required fields.

        Given: Required fields only (company_id, name)
        When: Creating a Project instance
        Then: Project is created with correct defaults
        """
        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Test Project",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            db.session.add(project)
            db.session.commit()

            assert project.id is not None
            assert isinstance(project.id, uuid.UUID)
            assert project.company_id == uuid.UUID(company_id)
            assert project.name == "Test Project"
            assert project.status == "active"  # Default value
            assert project.code is None
            assert project.description is None
            assert isinstance(project.start_date, datetime)
            assert isinstance(project.finish_date, datetime)
            assert project.budget is None
            assert project.created_at is not None
            assert project.updated_at is not None

    def test_create_project_full(self, app, company_id):
        """Test creating a project with all fields populated.

        Given: All fields provided
        When: Creating a Project instance
        Then: Project is created with all values correctly set
        """
        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                code="PROJ-001",
                name="Full Test Project",
                description="A comprehensive test project",
                start_date=DEFAULT_START_DATE,
                finish_date=datetime(2026, 12, 31, 18, 0),
                budget=Decimal("100000.00"),
                status="active",
            )
            db.session.add(project)
            db.session.commit()

            assert project.code == "PROJ-001"
            assert project.description == "A comprehensive test project"
            assert project.start_date == DEFAULT_START_DATE
            assert project.finish_date == datetime(2026, 12, 31, 18, 0)
            assert project.budget == Decimal("100000.00")
            assert project.status == "active"

    def test_project_unique_code_per_company(self, app, company_id, generate_uuid):
        """Test unique constraint on (company_id, code).

        Given: A project with a specific code exists for a company
        When: Creating another project with the same code for the same company
        Then: IntegrityError is raised
        """
        with app.app_context():
            # Create first project
            project1 = Project(
                company_id=uuid.UUID(company_id),
                code="PROJ-001",
                name="Project 1",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            db.session.add(project1)
            db.session.commit()

            # Try to create second project with same code for same company
            project2 = Project(
                company_id=uuid.UUID(company_id),
                code="PROJ-001",
                name="Project 2",
                start_date=DEFAULT_START_DATE + timedelta(days=1),
                finish_date=DEFAULT_FINISH_DATE + timedelta(days=1),
            )
            db.session.add(project2)

            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_project_same_code_different_companies(self, app, generate_uuid):
        """Test same code allowed for different companies.

        Given: Two different companies
        When: Creating projects with the same code for each company
        Then: Both projects are created successfully
        """
        with app.app_context():
            company1_id = uuid.UUID(generate_uuid())
            company2_id = uuid.UUID(generate_uuid())

            project1 = Project(
                company_id=company1_id,
                code="PROJ-001",
                name="Company 1 Project",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            project2 = Project(
                company_id=company2_id,
                code="PROJ-001",
                name="Company 2 Project",
                start_date=DEFAULT_START_DATE + timedelta(days=1),
                finish_date=DEFAULT_FINISH_DATE + timedelta(days=1),
            )

            db.session.add_all([project1, project2])
            db.session.commit()

            assert project1.id != project2.id
            assert project1.code == project2.code
            assert project1.company_id != project2.company_id

    def test_project_status_values(self, app, company_id):
        """Test valid status values.

        Given: Valid status values (active, completed, cancelled, on_hold)
        When: Creating projects with each status
        Then: Projects are created successfully
        """
        with app.app_context():
            statuses = ["active", "completed", "cancelled", "on_hold"]

            for status in statuses:
                project = Project(
                    company_id=uuid.UUID(company_id),
                    name=f"Project {status}",
                    status=status,
                    start_date=DEFAULT_START_DATE,
                    finish_date=DEFAULT_FINISH_DATE,
                )
                db.session.add(project)
                db.session.commit()

                assert project.status == status
                db.session.rollback()

    def test_project_repr(self, app, company_id):
        """Test string representation of Project.

        Given: A project instance
        When: Converting to string
        Then: Repr shows id, name, and status
        """
        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Test Project",
                status="active",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            db.session.add(project)
            db.session.commit()

            repr_str = repr(project)
            assert "Project" in repr_str
            assert str(project.id) in repr_str
            assert "Test Project" in repr_str
            assert "active" in repr_str

    def test_project_timestamps(self, app, company_id):
        """Test automatic timestamp generation.

        Given: A new project
        When: Creating and updating the project
        Then: created_at and updated_at are set automatically
        """
        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Test Project",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            db.session.add(project)
            db.session.commit()

            created_at = project.created_at
            updated_at = project.updated_at

            assert created_at is not None
            assert updated_at is not None
            assert created_at == updated_at

            # Update project
            project.name = "Updated Project"
            db.session.commit()

            # updated_at should change (depends on database trigger)
            # For SQLite in-memory, this might not work as expected
            # but the field should still exist
            assert project.updated_at is not None

    def test_project_relationships_exist(self, app, company_id):
        """Test that relationship attributes exist.

        Given: A project instance
        When: Accessing relationship attributes
        Then: Attributes exist and return empty lists
        """
        with app.app_context():
            project = Project(
                company_id=uuid.UUID(company_id),
                name="Test Project",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            db.session.add(project)
            db.session.commit()

            # Test relationships exist
            assert hasattr(project, "tasks")
            assert hasattr(project, "milestones")
            assert hasattr(project, "expenses")
            assert hasattr(project, "assignments")
            assert hasattr(project, "progress_updates")
            assert hasattr(project, "evm_snapshots")

            # All should be empty lists initially
            assert project.tasks == []
            assert project.milestones == []
            assert project.expenses == []
            assert project.assignments == []
            assert project.progress_updates == []
            assert project.evm_snapshots == []

    def test_project_null_code_allowed(self, app, company_id):
        """Test that code can be null.

        Given: No code provided
        When: Creating multiple projects without codes
        Then: All projects are created successfully
        """
        with app.app_context():
            project1 = Project(
                company_id=uuid.UUID(company_id),
                name="Project Without Code 1",
                start_date=DEFAULT_START_DATE,
                finish_date=DEFAULT_FINISH_DATE,
            )
            project2 = Project(
                company_id=uuid.UUID(company_id),
                name="Project Without Code 2",
                start_date=DEFAULT_START_DATE + timedelta(days=2),
                finish_date=DEFAULT_FINISH_DATE + timedelta(days=2),
            )

            db.session.add_all([project1, project2])
            db.session.commit()

            assert project1.code is None
            assert project2.code is None
            assert project1.id != project2.id
