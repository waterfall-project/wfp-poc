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
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

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
        description: Optional project description.
        start_date: Planned project start date.
        finish_date: Planned project finish date.
        budget_at_completion: Total planned budget (BAC).
        status: Project status (active, completed, cancelled, on_hold).
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

    start_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        doc="Planned start date",
    )

    finish_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        doc="Planned finish date",
    )

    budget_at_completion: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Total planned budget (BAC)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        doc="Project status",
    )

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        doc="Tasks in this project",
    )

    milestones: Mapped[list["Milestone"]] = relationship(
        "Milestone",
        back_populates="project",
        cascade="all, delete-orphan",
        doc="Milestones in this project",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="project",
        cascade="all, delete-orphan",
        doc="Expenses for this project",
    )

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="project",
        cascade="all, delete-orphan",
        doc="Resource assignments in this project",
    )

    progress_updates: Mapped[list["ProgressUpdate"]] = relationship(
        "ProgressUpdate",
        back_populates="project",
        cascade="all, delete-orphan",
        doc="Progress update history for this project",
    )

    evm_snapshots: Mapped[list["EVMSnapshot"]] = relationship(
        "EVMSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
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
            "status IN ('active', 'completed', 'cancelled', 'on_hold')",
            name="ck_projects_status",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Project.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"
