# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Milestone model definition.

This module defines the Milestone model for tracking key project deliverables
and decision points linked to specific dates and associated tasks. Milestones
are used for EVM milestone completion method and expense allocation.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.expense import Expense
    from app.models.milestone_task import MilestoneTask
    from app.models.project import Project
else:
    from app import db

    Model = db.Model


class Milestone(UUIDMixin, TimestampMixin, Model):
    """Milestone model for project milestone tracking.

    Represents a milestone in the project schedule, marking key deliverables
    or decision points. Milestones can be linked to one or more predecessor tasks.
    Used for EVM milestone completion method and expense allocation.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        ms_project_uid: MS Project unique ID for import reconciliation.
        name: Milestone name (required).
        description: Optional milestone description.
        target_date: Target completion date (required). Auto-calculated as
            MAX(predecessor_tasks.planned_finish_date) when tasks are linked.
        actual_date: Actual completion date (nullable).
        status: Milestone status (upcoming, achieved, missed). Auto-updated.
        budget_weight: Weight for EV milestone calculation (0.0-1.0, required).
            Sum across all project milestones must equal 1.0.
        is_achieved: True if milestone has been achieved (default False).
        achieved_date: Date when milestone was achieved (for EV milestone method).
        current_rae: Current Reste À Engager value (nullable).
        current_rae_date: Date of last RAE update (nullable).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "milestones"

    # Foreign Keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent project ID",
    )

    # Required Fields
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Milestone name",
    )

    target_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        doc="Target completion date (auto-calculated from predecessor tasks)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="upcoming",
        index=True,
        doc="Milestone status: upcoming, achieved, missed",
    )

    budget_weight: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),
        nullable=False,
        doc="Weight for EV milestone calculation (sum must equal 1.0 per project)",
    )

    is_achieved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="True if milestone has been achieved",
    )

    # Optional Fields
    ms_project_uid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project UID for import reconciliation",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Milestone description",
    )

    actual_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Actual milestone completion date",
    )

    achieved_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="Date when milestone was achieved (for EV milestone method)",
    )

    current_rae: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=True,
        doc="Current Reste À Engager value",
    )

    current_rae_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Date of last RAE update",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="milestones",
        doc="Parent project",
    )

    task_links: Mapped[list["MilestoneTask"]] = relationship(
        "MilestoneTask",
        back_populates="milestone",
        cascade="all, delete-orphan",
        doc="Linked tasks for this milestone",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="milestone",
        doc="Expenses allocated to this milestone",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "ms_project_uid",
            name="uq_milestones_project_uid",
        ),
        CheckConstraint(
            "status IN ('upcoming', 'achieved', 'missed')",
            name="ck_milestones_status",
        ),
        CheckConstraint(
            "budget_weight >= 0 AND budget_weight <= 1",
            name="ck_milestones_budget_weight_range",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Milestone.

        Returns:
            Human-readable string with key attributes.
        """
        return (
            f"<Milestone(id={self.id}, name='{self.name}', "
            f"status='{self.status}', budget_weight={self.budget_weight})>"
        )

    @staticmethod
    def _normalize_datetime(value: datetime | date | None) -> datetime | None:
        """Normalize datetimes to naive UTC for storage consistency.

        Converts date inputs to midnight datetimes and strips timezone
        information while preserving the absolute UTC instant.

        Args:
            value: Date or datetime value to normalize.

        Returns:
            Naive datetime or None.
        """
        if value is None:
            return None

        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())

        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)

        return value

    @validates("target_date", "actual_date", "achieved_date", "current_rae_date")
    def _validate_datetime_field(
        self, key: str, value: datetime | date | None
    ) -> datetime | None:
        """Ensure datetime fields are stored as naive UTC values."""
        return self._normalize_datetime(value)
