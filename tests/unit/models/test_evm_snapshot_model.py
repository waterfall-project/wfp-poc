# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for EVMSnapshot model.

Tests cover model creation, validation, constraints, relationships,
and business logic for the EVMSnapshot (Earned Value Management) entity.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import EVMSnapshot, Project, db

DEFAULT_START_DATE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEFAULT_FINISH_DATE = datetime(2026, 1, 31, 18, 0, tzinfo=UTC)


class TestEVMSnapshotModel:
    """Test suite for EVMSnapshot model."""

    @pytest.fixture
    def project(self, app, company_id):
        """Create a test project."""
        project = Project(
            company_id=uuid.UUID(company_id),
            name="Test Project",
            start_date=DEFAULT_START_DATE,
            finish_date=DEFAULT_FINISH_DATE,
            budget=Decimal("100000.00"),
        )
        db.session.add(project)
        db.session.commit()
        db.session.refresh(project)
        return project

    def test_create_evm_snapshot_minimal(self, app, project):
        """Test creating an EVM snapshot with minimal required fields.

        Given: Required fields only (project_id, status_date)
        When: Creating an EVMSnapshot instance
        Then: Snapshot is created with correct defaults
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
        )
        db.session.add(snapshot)
        db.session.commit()

        assert snapshot.id is not None
        assert isinstance(snapshot.id, uuid.UUID)
        assert snapshot.project_id == project.id
        assert snapshot.status_date == date(2026, 6, 1)
        # All EVM metrics should default to None or 0
        assert snapshot.planned_value is None
        assert snapshot.earned_value is None
        assert snapshot.actual_cost is None
        assert snapshot.created_at is not None
        assert snapshot.updated_at is not None

    def test_create_evm_snapshot_full(self, app, project):
        """Test creating an EVM snapshot with all metrics populated.

        Given: All EVM metric fields provided
        When: Creating an EVMSnapshot instance
        Then: Snapshot is created with all values correctly set
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 15),
            # Core metrics (PV, EV, AC)
            planned_value=Decimal("50000.00"),
            earned_value=Decimal("45000.00"),
            actual_cost=Decimal("48000.00"),
            # Budget metrics
            budget_at_completion=Decimal("100000.00"),
            estimate_at_completion=Decimal("106667.00"),
            estimate_to_complete=Decimal("58667.00"),
            variance_at_completion=Decimal("-6667.00"),
            # Variance metrics
            schedule_variance=Decimal("-5000.00"),
            cost_variance=Decimal("-3000.00"),
            # Performance indices
            schedule_performance_index=Decimal("0.90"),
            cost_performance_index=Decimal("0.94"),
            to_complete_performance_index=Decimal("1.13"),
        )
        db.session.add(snapshot)
        db.session.commit()

        assert snapshot.id is not None
        assert snapshot.planned_value == Decimal("50000.00")
        assert snapshot.earned_value == Decimal("45000.00")
        assert snapshot.actual_cost == Decimal("48000.00")
        assert snapshot.budget_at_completion == Decimal("100000.00")
        assert snapshot.estimate_at_completion == Decimal("106667.00")
        assert snapshot.schedule_variance == Decimal("-5000.00")
        assert snapshot.cost_variance == Decimal("-3000.00")
        assert snapshot.schedule_performance_index == Decimal("0.90")
        assert snapshot.cost_performance_index == Decimal("0.94")

    def test_evm_snapshot_multiple_per_project(self, app, project):
        """Test multiple EVM snapshots for same project.

        Given: One project
        When: Creating multiple snapshots for different dates
        Then: All snapshots are created successfully
        """
        snapshot1 = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 1, 31),
            planned_value=Decimal("10000.00"),
            earned_value=Decimal("9000.00"),
        )
        snapshot2 = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 2, 28),
            planned_value=Decimal("20000.00"),
            earned_value=Decimal("19000.00"),
        )
        db.session.add_all([snapshot1, snapshot2])
        db.session.commit()

        assert snapshot1.project_id == project.id
        assert snapshot2.project_id == project.id
        assert snapshot1.status_date != snapshot2.status_date

    def test_evm_snapshot_calculated_metrics(self, app, project):
        """Test EVM calculated metrics (SV, CV, SPI, CPI).

        Given: Base metrics (PV, EV, AC)
        When: Storing calculated variance and index values
        Then: Calculations are consistent with EVM formulas
        """
        # Given: PV=50000, EV=45000, AC=48000, BAC=100000
        pv = Decimal("50000.00")
        ev = Decimal("45000.00")
        ac = Decimal("48000.00")
        bac = Decimal("100000.00")

        # Calculate metrics
        sv = ev - pv  # -5000 (behind schedule)
        cv = ev - ac  # -3000 (over budget)
        spi = ev / pv  # 0.90
        cpi = ev / ac  # 0.9375
        eac = bac / cpi  # 106667
        etc = eac - ac  # 58667
        vac = bac - eac  # -6667
        tcpi = (bac - ev) / (bac - ac)  # 1.057

        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 15),
            planned_value=pv,
            earned_value=ev,
            actual_cost=ac,
            budget_at_completion=bac,
            schedule_variance=sv,
            cost_variance=cv,
            schedule_performance_index=spi,
            cost_performance_index=cpi.quantize(Decimal("0.01")),
            estimate_at_completion=eac.quantize(Decimal("0.01")),
            estimate_to_complete=etc.quantize(Decimal("0.01")),
            variance_at_completion=vac.quantize(Decimal("0.01")),
            to_complete_performance_index=tcpi.quantize(Decimal("0.01")),
        )
        db.session.add(snapshot)
        db.session.commit()

        # Verify stored values
        assert snapshot.schedule_variance == Decimal("-5000.00")
        assert snapshot.cost_variance == Decimal("-3000.00")
        assert snapshot.schedule_performance_index == Decimal("0.90")
        assert snapshot.cost_performance_index == Decimal("0.94")

    def test_evm_snapshot_decimal_precision(self, app, project):
        """Test decimal precision for all monetary fields.

        Given: EVM metrics with decimal values
        When: Setting values with various decimal places
        Then: Precision is maintained (2 decimal places)
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
            planned_value=Decimal("12345.67"),
            earned_value=Decimal("12300.50"),
            actual_cost=Decimal("12450.75"),
            budget_at_completion=Decimal("100000.00"),
        )
        db.session.add(snapshot)
        db.session.commit()

        assert snapshot.planned_value == Decimal("12345.67")
        assert snapshot.earned_value == Decimal("12300.50")
        assert snapshot.actual_cost == Decimal("12450.75")

    def test_evm_snapshot_performance_index_precision(self, app, project):
        """Test decimal precision for performance indices.

        Given: Performance indices (SPI, CPI, TCPI)
        When: Setting values with multiple decimal places
        Then: Precision is maintained (4 decimal places)
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
            schedule_performance_index=Decimal("0.9523"),
            cost_performance_index=Decimal("1.0456"),
            to_complete_performance_index=Decimal("1.1234"),
        )
        db.session.add(snapshot)
        db.session.commit()

        assert snapshot.schedule_performance_index == Decimal("0.9523")
        assert snapshot.cost_performance_index == Decimal("1.0456")
        assert snapshot.to_complete_performance_index == Decimal("1.1234")

    def test_evm_snapshot_project_health_indicators(self, app, project):
        """Test EVM health indicators scenario.

        Given: A snapshot with poor performance metrics
        When: Analyzing SPI and CPI
        Then: Project health can be assessed
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
            planned_value=Decimal("50000.00"),
            earned_value=Decimal("40000.00"),
            actual_cost=Decimal("45000.00"),
            schedule_performance_index=Decimal("0.80"),  # Behind schedule
            cost_performance_index=Decimal("0.89"),  # Over budget
        )
        db.session.add(snapshot)
        db.session.commit()

        # SPI < 1.0 indicates behind schedule
        assert snapshot.schedule_performance_index is not None
        assert snapshot.schedule_performance_index < Decimal("1.0")
        # CPI < 1.0 indicates over budget
        assert snapshot.cost_performance_index is not None
        assert snapshot.cost_performance_index < Decimal("1.0")

    def test_evm_snapshot_repr(self, app, project):
        """Test string representation of EVMSnapshot.

        Given: An EVM snapshot instance
        When: Converting to string
        Then: Repr shows id, project_id, and status_date
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
        )
        db.session.add(snapshot)
        db.session.commit()

        repr_str = repr(snapshot)
        assert "EVMSnapshot" in repr_str
        assert str(snapshot.id) in repr_str

    def test_evm_snapshot_relationships_exist(self, app, project):
        """Test that relationship attributes exist.

        Given: An EVM snapshot instance
        When: Accessing relationship attributes
        Then: Attributes exist and return correct values
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
        )
        db.session.add(snapshot)
        db.session.commit()

        # Check relationship attributes exist
        assert hasattr(snapshot, "project")
        assert snapshot.project == project

    def test_evm_snapshot_cascade_delete(self, app, project):
        """Test cascade delete when project is deleted.

        Given: An EVM snapshot linked to a project
        When: Deleting the project
        Then: Snapshot is also deleted
        """
        snapshot = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 6, 1),
        )
        db.session.add(snapshot)
        db.session.commit()

        snapshot_id = snapshot.id

        # Delete project
        db.session.delete(project)
        db.session.commit()

        # Verify snapshot was deleted
        deleted_snapshot = db.session.get(EVMSnapshot, snapshot_id)
        assert deleted_snapshot is None

    def test_evm_snapshot_temporal_ordering(self, app, project):
        """Test chronological ordering of snapshots.

        Given: Multiple snapshots for different dates
        When: Querying by status_date
        Then: Snapshots can be ordered chronologically
        """
        snapshot1 = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 3, 31),
            earned_value=Decimal("30000.00"),
        )
        snapshot2 = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 1, 31),
            earned_value=Decimal("10000.00"),
        )
        snapshot3 = EVMSnapshot(
            project_id=project.id,
            status_date=date(2026, 2, 28),
            earned_value=Decimal("20000.00"),
        )
        db.session.add_all([snapshot1, snapshot2, snapshot3])
        db.session.commit()

        # Query snapshots ordered by date
        snapshots = (
            db.session.query(EVMSnapshot)
            .filter_by(project_id=project.id)
            .order_by(EVMSnapshot.status_date)
            .all()
        )

        assert len(snapshots) == 3
        assert snapshots[0].status_date == date(2026, 1, 31)
        assert snapshots[1].status_date == date(2026, 2, 28)
        assert snapshots[2].status_date == date(2026, 3, 31)
