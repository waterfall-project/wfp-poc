# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Milestone-Task link model definition.

This module defines the MilestoneTask model for associating tasks
with project milestones in a many-to-many relationship.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.milestone import Milestone
    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class MilestoneTask(UUIDMixin, TimestampMixin, Model):
    """Milestone-Task association model.

    Represents a many-to-many link between milestones and tasks,
    allowing a milestone to track completion of multiple related tasks.

    Attributes:
        id: Unique identifier (UUID, primary key).
        milestone_id: Milestone identifier (UUID, required, foreign key).
        task_id: Task identifier (UUID, required, foreign key).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "milestone_tasks"

    # Foreign Keys
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("milestones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Milestone ID",
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Task ID",
    )

    # Relationships
    milestone: Mapped["Milestone"] = relationship(
        "Milestone",
        back_populates="task_links",
        doc="Associated milestone",
    )

    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="milestone_links",
        doc="Associated task",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "milestone_id",
            "task_id",
            name="uq_milestone_tasks_pair",
        ),
    )

    def __repr__(self) -> str:
        """String representation of MilestoneTask.

        Returns:
            Human-readable string with key attributes.
        """
        return (
            f"<MilestoneTask(milestone_id={self.milestone_id}, task_id={self.task_id})>"
        )
