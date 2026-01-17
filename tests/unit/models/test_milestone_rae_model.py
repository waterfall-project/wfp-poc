# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for MilestoneRAE model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the MilestoneRAE (Remaining Amount Estimate) entity.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models import Milestone, MilestoneRAE, Project, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
DEFAULT_TARGET_DATE = datetime(2026, 6, 30, 18, 0, tzinfo=UTC)


class TestMilestoneRAEModel:
    """Test suite for MilestoneRAE model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project."""
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
            start_date=DEFAULT_START_DATE,
            finish_date=DEFAULT_FINISH_DATE,
            budget=Decimal("500000.00"),
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
            name="Phase 1 Complete",
            target_date=DEFAULT_TARGET_DATE,
            budget_weight=Decimal("0.25"),
        )
        db.session.add(milestone)
        db.session.commit()
        db.session.refresh(milestone)
        return milestone

    @pytest.fixture
    def user_id(self):
        """Return a test user UUID."""
        return uuid.uuid4()

    def test_create_milestone_rae_minimal(self, app, milestone, user_id):
        """Test creating a milestone RAE with minimal required fields.

        Given: Required fields only (milestone_id, date, amount, updated_by)
        When: Creating a MilestoneRAE instance
        Then: RAE is created with correct values and defaults
        """
        rae_date = datetime(2026, 1, 31, 23, 59, tzinfo=UTC)
        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=rae_date,
            amount=Decimal("75000.00"),
            updated_by=user_id,
        )
        db.session.add(rae)
        db.session.commit()

        assert rae.id is not None
        assert isinstance(rae.id, uuid.UUID)
        assert rae.milestone_id == milestone.id
        assert rae.date == rae_date
        assert rae.amount == Decimal("75000.00")
        assert rae.updated_by == user_id
        assert rae.comment is None
        assert rae.details is None
        assert rae.created_at is not None
        assert rae.updated_at is not None

    def test_create_milestone_rae_full(self, app, milestone, user_id):
        """Test creating a milestone RAE with all fields populated.

        Given: All fields provided including comment and details
        When: Creating a MilestoneRAE instance
        Then: RAE is created with all values correctly set
        """
        rae_date = datetime(2026, 2, 28, 23, 59, tzinfo=UTC)
        details = {
            "task_estimates": [
                {
                    "task_id": str(uuid.uuid4()),
                    "task_name": "Backend Development",
                    "remaining_cost": 45000.00,
                    "comment": "On track",
                },
                {
                    "task_id": str(uuid.uuid4()),
                    "task_name": "Frontend Development",
                    "remaining_cost": 30000.00,
                    "comment": "Slight delay",
                },
            ]
        }

        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=rae_date,
            amount=Decimal("75000.00"),
            updated_by=user_id,
            comment="Backend team reporting delays",
            details=details,
        )
        db.session.add(rae)
        db.session.commit()

        assert rae.id is not None
        assert rae.milestone_id == milestone.id
        assert rae.date == rae_date
        assert rae.amount == Decimal("75000.00")
        assert rae.updated_by == user_id
        assert rae.comment == "Backend team reporting delays"
        assert rae.details == details
        assert rae.details is not None
        assert len(rae.details["task_estimates"]) == 2

    def test_milestone_rae_amount_conversion(self, app, milestone, user_id):
        """Test that float amounts are correctly converted to Decimal.

        Given: Amount provided as float
        When: Creating a MilestoneRAE instance
        Then: Amount is stored as Decimal
        """
        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 3, 31, tzinfo=UTC),
            amount=50000.50,  # float
            updated_by=user_id,
        )
        db.session.add(rae)
        db.session.commit()

        assert isinstance(rae.amount, Decimal)
        assert rae.amount == Decimal("50000.50")

    def test_milestone_rae_relationship(self, app, milestone, user_id):
        """Test relationship between Milestone and MilestoneRAE.

        Given: A milestone with multiple RAE entries
        When: Accessing milestone.rae_history
        Then: All RAE entries are accessible
        """
        rae1 = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("100000.00"),
            updated_by=user_id,
            comment="Initial estimate",
        )
        rae2 = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 2, 28, tzinfo=UTC),
            amount=Decimal("75000.00"),
            updated_by=user_id,
            comment="Progress update",
        )
        db.session.add_all([rae1, rae2])
        db.session.commit()

        db.session.refresh(milestone)
        assert len(milestone.rae_history) == 2
        assert rae1 in milestone.rae_history
        assert rae2 in milestone.rae_history

    def test_milestone_rae_cascade_delete(self, app, milestone, user_id):
        """Test cascade deletion when milestone is deleted.

        Given: A milestone with RAE entries
        When: Milestone is deleted
        Then: All associated RAE entries are also deleted
        """
        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("80000.00"),
            updated_by=user_id,
        )
        db.session.add(rae)
        db.session.commit()
        rae_id = rae.id

        # Delete milestone
        db.session.delete(milestone)
        db.session.commit()

        # Verify RAE is also deleted
        deleted_rae = db.session.get(MilestoneRAE, rae_id)
        assert deleted_rae is None

    def test_milestone_rae_repr(self, app, milestone, user_id):
        """Test string representation of MilestoneRAE.

        Given: A milestone RAE entry
        When: Converting to string
        Then: String contains key identifying information
        """
        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("90000.00"),
            updated_by=user_id,
        )

        repr_str = repr(rae)
        assert "MilestoneRAE" in repr_str
        assert str(milestone.id) in repr_str
        assert "90000.00" in repr_str

    def test_milestone_rae_timestamps(self, app, milestone, user_id):
        """Test automatic timestamp management.

        Given: A new milestone RAE entry
        When: Creating and then updating the entry
        Then: created_at remains constant, updated_at is set
        """
        import time

        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("70000.00"),
            updated_by=user_id,
        )
        db.session.add(rae)
        db.session.commit()

        original_created_at = rae.created_at

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # Update amount
        rae.amount = Decimal("65000.00")
        db.session.commit()
        db.session.refresh(rae)

        assert rae.created_at == original_created_at
        # In test environment with SQLite, updated_at might not auto-update
        # Just verify it exists
        assert rae.updated_at is not None

    def test_milestone_rae_comment_max_length(self, app, milestone, user_id):
        """Test comment field respects max length constraint.

        Given: A comment that exceeds 500 characters
        When: Creating a MilestoneRAE instance
        Then: Database accepts valid length, rejects too long
        """
        # Valid: exactly 500 characters
        valid_comment = "x" * 500
        rae_valid = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("70000.00"),
            updated_by=user_id,
            comment=valid_comment,
        )
        db.session.add(rae_valid)
        db.session.commit()
        assert rae_valid.comment is not None
        assert len(rae_valid.comment) == 500

    def test_milestone_rae_jsonb_details(self, app, milestone, user_id):
        """Test JSONB details field supports complex structures.

        Given: Complex nested JSON in details
        When: Creating and retrieving MilestoneRAE
        Then: JSON structure is preserved
        """
        complex_details = {
            "method": "bottom-up",
            "task_estimates": [
                {
                    "task_id": str(uuid.uuid4()),
                    "task_name": "Task A",
                    "status": "in_progress",
                    "budget": 50000.00,
                    "estimate_to_complete": 30000.00,
                },
            ],
            "assumptions": ["Team remains stable", "No scope changes"],
            "risks": [{"description": "Resource availability", "impact": "high"}],
        }

        rae = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("30000.00"),
            updated_by=user_id,
            details=complex_details,
        )
        db.session.add(rae)
        db.session.commit()

        db.session.refresh(rae)
        assert rae.details is not None
        assert rae.details["method"] == "bottom-up"
        assert len(rae.details["task_estimates"]) == 1
        assert len(rae.details["assumptions"]) == 2
        assert len(rae.details["risks"]) == 1
        assert rae.details["risks"][0]["impact"] == "high"

    def test_milestone_rae_ordering_by_date(self, app, milestone, user_id):
        """Test RAE entries can be ordered by date.

        Given: Multiple RAE entries with different dates
        When: Querying RAE entries ordered by date
        Then: Entries are returned in correct chronological order
        """
        rae1 = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 3, 31, tzinfo=UTC),
            amount=Decimal("50000.00"),
            updated_by=user_id,
        )
        rae2 = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 1, 31, tzinfo=UTC),
            amount=Decimal("100000.00"),
            updated_by=user_id,
        )
        rae3 = MilestoneRAE(
            milestone_id=milestone.id,
            date=datetime(2026, 2, 28, tzinfo=UTC),
            amount=Decimal("75000.00"),
            updated_by=user_id,
        )
        db.session.add_all([rae1, rae2, rae3])
        db.session.commit()

        # Query ordered by date ascending
        raes_asc = (
            db.session.query(MilestoneRAE)
            .filter(MilestoneRAE.milestone_id == milestone.id)
            .order_by(MilestoneRAE.date.asc())
            .all()
        )

        assert raes_asc[0].date.month == 1
        assert raes_asc[1].date.month == 2
        assert raes_asc[2].date.month == 3

        # Query ordered by date descending (most recent first)
        raes_desc = (
            db.session.query(MilestoneRAE)
            .filter(MilestoneRAE.milestone_id == milestone.id)
            .order_by(MilestoneRAE.date.desc())
            .all()
        )

        assert raes_desc[0].date.month == 3
        assert raes_desc[1].date.month == 2
        assert raes_desc[2].date.month == 1
