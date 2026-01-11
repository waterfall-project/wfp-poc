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
and decision points linked to specific dates and associated tasks.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.milestone_task import MilestoneTask
    from app.models.project import Project
else:
    from app import db

    Model = db.Model


class Milestone(UUIDMixin, TimestampMixin, Model):
    """Milestone model for project milestone tracking.

    Represents a milestone in the project schedule, marking key deliverables
    or decision points. Milestones can be linked to one or more tasks.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        ms_project_uid: MS Project unique ID for import reconciliation.
        name: Milestone name (required).
        description: Optional milestone description.
        planned_date: Planned milestone date.
        actual_date: Actual milestone achievement date (nullable).
        status: Milestone status (not_reached, reached, missed).
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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_reached",
        index=True,
        doc="Milestone status: not_reached, reached, missed",
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

    planned_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        doc="Planned milestone date",
    )

    actual_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        doc="Actual milestone achievement date",
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

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "ms_project_uid",
            name="uq_milestones_project_uid",
        ),
        CheckConstraint(
            "status IN ('not_reached', 'reached', 'missed')",
            name="ck_milestones_status",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Milestone.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Milestone(id={self.id}, name='{self.name}', status='{self.status}')>"
