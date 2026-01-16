# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Project model definition.

This module defines the Project model for managing projects within
the EVM system with multi-tenancy support and comprehensive tracking.
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.types import GUID, TimestampMixin, UUIDMixin

CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.assignment import Assignment
    from app.models.evm_snapshot import EVMSnapshot
    from app.models.expense import Expense
    from app.models.milestone import Milestone
    from app.models.progress_update import ProgressUpdate
    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class Project(UUIDMixin, TimestampMixin, Model):
    """Project model for EVM project management.

    Represents a project in the system with planning dates, budget,
    and multi-tenancy isolation by company.

    Attributes:
        id: Unique identifier (UUID, primary key).
        company_id: Company identifier for multi-tenancy (UUID, required).
        code: Optional unique project code within company.
        name: Project name (required, max 255 characters).
        title: Optional MS Project title field.
        description: Optional project description.
        planned_start_date: Deprecated alias for start_date.
        planned_finish_date: Deprecated alias for finish_date.
        start_date: Planned project start date (required, date-time).
        finish_date: Planned project finish date (required, date-time).
        budget: Total planned budget (BAC).
        currency_code: ISO 4217 currency code, default EUR.
        status: Project status (active, completed, cancelled, on_hold).
        ms_project_uid: MS Project UID (string/integer representation).
        ms_project_guid: MS Project GUID for reconciliation.
        ms_project_save_version: MS Project SaveVersion field.
        creation_date: Original MS Project creation date.
        last_saved_date: MS Project last saved date.
        calendar_uid: MS Project calendar UID.
        minutes_per_day: Working minutes per day.
        minutes_per_week: Working minutes per week.
        days_per_month: Working days per month.
        week_start_day: Week start day (0=Sunday,1=Monday).
        default_start_time: Default task start time (HH:MM:SS).
        default_finish_time: Default task finish time (HH:MM:SS).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "projects"

    # Required Fields
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        nullable=False,
        index=True,
        doc="Company ID for multi-tenancy isolation",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Project name",
    )

    # Optional Fields
    code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Unique project code within company",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Project description",
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="MS Project title",
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        doc="Planned start date",
    )

    planned_start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Deprecated alias for start_date",
    )

    finish_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        doc="Planned finish date",
    )

    planned_finish_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Deprecated alias for finish_date",
    )

    budget: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        doc="Total planned budget (BAC)",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
        doc="ISO 4217 currency code",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="initialized",
        index=True,
        doc="Project status",
    )

    ms_project_uid: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="MS Project UID",
    )

    ms_project_guid: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="MS Project GUID",
    )

    ms_project_save_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project SaveVersion",
    )

    creation_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Original MS Project creation date",
    )

    last_saved_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="MS Project last saved date",
    )

    calendar_uid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project calendar UID",
    )

    minutes_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=420,
        doc="Working minutes per day",
    )

    minutes_per_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2100,
        doc="Working minutes per week",
    )

    days_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=20,
        doc="Working days per month",
    )

    week_start_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Week start day (0=Sunday,1=Monday)",
    )

    default_start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(9, 0, 0),
        doc="Default task start time",
    )

    default_finish_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(18, 0, 0),
        doc="Default task finish time",
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Tasks in this project",
    )

    milestones: Mapped[list["Milestone"]] = relationship(
        "Milestone",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Milestones in this project",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Expenses for this project",
    )

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Resource assignments in this project",
    )

    progress_updates: Mapped[list["ProgressUpdate"]] = relationship(
        "ProgressUpdate",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Progress update history for this project",
    )

    evm_snapshots: Mapped[list["EVMSnapshot"]] = relationship(
        "EVMSnapshot",
        back_populates="project",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="EVM calculation snapshots for this project",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_projects_company_code",
        ),
        CheckConstraint(
            "status IN ('initialized', 'active', 'completed', 'cancelled', 'on_hold')",
            name="ck_projects_status",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Project.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"

    @staticmethod
    def _normalize_datetime(value: datetime | date | None) -> datetime | None:
        """Normalize datetimes to naive UTC for consistent storage."""
        if value is None:
            return None

        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())

        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)

        return value

    @validates(
        "start_date",
        "planned_start_date",
        "finish_date",
        "planned_finish_date",
        "creation_date",
        "last_saved_date",
    )
    def _validate_datetime_field(
        self, key: str, value: datetime | date | None
    ) -> datetime | None:
        """Ensure project datetime fields are stored as naive UTC values."""
        return self._normalize_datetime(value)
