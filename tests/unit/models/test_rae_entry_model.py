# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for RAEEntry model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the RAEEntry (Risk, Assumption, Exception) entity.
"""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.models import Project, RAEEntry, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestRAEEntryModel:
    """Test suite for RAEEntry model."""

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
    def task(self, app, project):
        """Create a test task."""
        from app.models import Task

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

    def test_create_rae_entry_minimal(self, app, task):
        """Test creating an RAE entry with minimal required fields.

        Given: Required fields only (task_id, type, description)
        When: Creating an RAEEntry instance
        Then: Entry is created with correct defaults
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Test Risk",
        )
        db.session.add(rae_entry)
        db.session.commit()

        assert rae_entry.id is not None
        assert isinstance(rae_entry.id, uuid.UUID)
        assert rae_entry.task_id == task.id
        assert rae_entry.type == "risk"
        assert rae_entry.description == "Test Risk"
        assert rae_entry.category == "other"  # Default value
        assert rae_entry.severity == "medium"  # Default value
        assert rae_entry.status == "open"  # Default value
        assert rae_entry.mitigation is None
        assert rae_entry.identified_date is None
        assert rae_entry.resolution_date is None
        assert rae_entry.details is None  # JSONB nullable
        assert rae_entry.created_at is not None
        assert rae_entry.updated_at is not None

    def test_create_rae_entry_full(self, app, task):
        """Test creating an RAE entry with all fields populated.

        Given: All fields provided
        When: Creating an RAEEntry instance
        Then: Entry is created with all values correctly set
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            category="technical",
            description="A comprehensive risk description",
            mitigation="Implement backup system and monitoring",
            severity="high",
            status="mitigated",
            identified_date=date(2026, 1, 15),
            resolution_date=date(2026, 2, 20),
            details={
                "probability": "high",
                "impact": "critical",
                "owner": "John Doe",
            },
        )
        db.session.add(rae_entry)
        db.session.commit()

        assert rae_entry.id is not None
        assert rae_entry.type == "risk"
        assert rae_entry.category == "technical"
        assert rae_entry.description == "A comprehensive risk description"
        assert rae_entry.mitigation == "Implement backup system and monitoring"
        assert rae_entry.severity == "high"
        assert rae_entry.status == "mitigated"
        assert rae_entry.identified_date == date(2026, 1, 15)
        assert rae_entry.resolution_date == date(2026, 2, 20)
        assert rae_entry.details is not None
        assert rae_entry.details["probability"] == "high"
        assert rae_entry.details["impact"] == "critical"

    def test_rae_entry_type_values(self, app, task):
        """Test valid type values.

        Given: Valid type values (risk, assumption, exception)
        When: Creating entries with each type
        Then: Entries are created successfully
        """
        types = ["risk", "assumption", "exception"]

        for entry_type in types:
            rae_entry = RAEEntry(
                task_id=task.id,
                type=entry_type,
                description=f"Test {entry_type}",
            )
            db.session.add(rae_entry)
            db.session.commit()

            assert rae_entry.type == entry_type

    def test_rae_entry_category_values(self, app, task):
        """Test valid category values.

        Given: Valid category values (technical, financial, schedule, resource, quality, other)
        When: Creating entries with each category
        Then: Entries are created successfully
        """
        categories = [
            "technical",
            "financial",
            "schedule",
            "resource",
            "quality",
            "other",
        ]

        for category in categories:
            rae_entry = RAEEntry(
                task_id=task.id,
                type="risk",
                description=f"Test Risk {category}",
                category=category,
            )
            db.session.add(rae_entry)
            db.session.commit()

            assert rae_entry.category == category

    def test_rae_entry_severity_values(self, app, task):
        """Test valid severity values.

        Given: Valid severity values (low, medium, high, critical)
        When: Creating entries with each severity
        Then: Entries are created successfully
        """
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            rae_entry = RAEEntry(
                task_id=task.id,
                type="risk",
                description=f"Test Risk {severity}",
                severity=severity,
            )
            db.session.add(rae_entry)
            db.session.commit()

            assert rae_entry.severity == severity

    def test_rae_entry_status_values(self, app, task):
        """Test valid status values.

        Given: Valid status values (open, mitigated, resolved, closed)
        When: Creating entries with each status
        Then: Entries are created successfully
        """
        statuses = ["open", "mitigated", "resolved", "closed"]

        for status in statuses:
            rae_entry = RAEEntry(
                task_id=task.id,
                type="risk",
                description=f"Test Risk {status}",
                status=status,
            )
            db.session.add(rae_entry)
            db.session.commit()

            assert rae_entry.status == status

    def test_rae_entry_jsonb_details(self, app, task):
        """Test JSONB details field with various structures.

        Given: An RAE entry with JSONB details
        When: Storing complex nested JSON data
        Then: Data is stored and retrieved correctly
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Risk with JSONB",
            details={
                "assessment": {
                    "probability": 0.7,
                    "impact_cost": 50000,
                    "impact_schedule_days": 14,
                },
                "mitigation": {
                    "strategy": "avoid",
                    "actions": ["Task A", "Task B", "Task C"],
                },
                "contingency_budget": 10000,
            },
        )
        db.session.add(rae_entry)
        db.session.commit()

        # Retrieve and verify nested structure
        assert rae_entry.details is not None
        assert rae_entry.details["assessment"]["probability"] == pytest.approx(0.7)
        assert rae_entry.details["assessment"]["impact_cost"] == 50000
        assert len(rae_entry.details["mitigation"]["actions"]) == 3
        assert rae_entry.details["contingency_budget"] == 10000

    def test_rae_entry_identified_vs_resolution_date(self, app, task):
        """Test identified vs resolution date tracking.

        Given: An RAE entry with identified date
        When: Setting resolution date later
        Then: Both dates are tracked independently
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Date Tracking Risk",
            identified_date=date(2026, 1, 10),
        )
        db.session.add(rae_entry)
        db.session.commit()

        assert rae_entry.identified_date == date(2026, 1, 10)
        assert rae_entry.resolution_date is None

        # Update resolution date
        rae_entry.resolution_date = date(2026, 2, 15)
        db.session.commit()

        assert rae_entry.resolution_date == date(2026, 2, 15)
        assert rae_entry.identified_date == date(2026, 1, 10)

    def test_rae_entry_lifecycle_workflow(self, app, task):
        """Test typical RAE entry lifecycle workflow.

        Given: A new risk entry
        When: Moving through statuses (open -> mitigated -> resolved)
        Then: Status transitions work correctly
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Lifecycle Test Risk",
            status="open",
            identified_date=date(2026, 1, 1),
        )
        db.session.add(rae_entry)
        db.session.commit()

        assert rae_entry.status == "open"

        # Move to mitigated
        rae_entry.status = "mitigated"
        db.session.commit()
        assert rae_entry.status == "mitigated"

        # Resolve
        rae_entry.status = "resolved"
        rae_entry.resolution_date = date(2026, 1, 30)
        db.session.commit()
        assert rae_entry.status == "resolved"
        assert rae_entry.resolution_date == date(2026, 1, 30)

    def test_rae_entry_repr(self, app, task):
        """Test string representation of RAEEntry.

        Given: An RAE entry instance
        When: Converting to string
        Then: Repr shows id, type, severity, and status
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Test Risk",
        )
        db.session.add(rae_entry)
        db.session.commit()

        repr_str = repr(rae_entry)
        assert "RAEEntry" in repr_str
        assert str(rae_entry.id) in repr_str
        assert rae_entry.type in repr_str
        assert rae_entry.severity in repr_str
        assert rae_entry.status in repr_str

    def test_rae_entry_relationships_exist(self, app, task):
        """Test that relationship attributes exist.

        Given: An RAE entry instance
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Test Risk",
        )
        db.session.add(rae_entry)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(rae_entry, "task")
        assert rae_entry.task == task

    def test_rae_entry_cascade_delete(self, app, task):
        """Test cascade delete when task is deleted.

        Given: An RAE entry linked to a task
        When: Deleting the task
        Then: RAE entry is also deleted
        """
        rae_entry = RAEEntry(
            task_id=task.id,
            type="risk",
            description="Test Risk",
        )
        db.session.add(rae_entry)
        db.session.commit()

        entry_id = rae_entry.id

        # Delete task
        db.session.delete(task)
        db.session.commit()

        # Verify RAE entry was deleted
        deleted_entry = db.session.get(RAEEntry, entry_id)
        assert deleted_entry is None
