# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Progress update model definition.

This module defines the ProgressUpdate model for tracking historical
progress snapshots of projects and tasks over time.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.project import Project
    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class ProgressUpdate(UUIDMixin, TimestampMixin, Model):
    """Progress update model for historical progress tracking.

    Stores periodic snapshots of progress for projects or tasks,
    capturing percent complete, EVM metrics, and notes at specific dates.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        task_id: Optional task identifier for task-level updates (UUID, nullable, foreign key).
        update_date: Date of this progress snapshot (required).
        percent_complete: Physical completion percentage (0-100).
        earned_value: Earned Value (EV) at this date.
        actual_cost: Actual Cost (AC) at this date.
        notes: Optional progress notes or comments.
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "progress_updates"

    # Foreign Keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent project ID",
    )

    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Optional task ID for task-level updates",
    )

    # Required Fields
    update_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        doc="Date of this progress snapshot",
    )

    percent_complete: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.0,
        doc="Physical completion percentage (0-100)",
    )

    # Optional Fields
    earned_value: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Earned Value (EV) at this date",
    )

    actual_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Actual Cost (AC) at this date",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional progress notes or comments",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="progress_updates",
        doc="Parent project",
    )

    task: Mapped["Task | None"] = relationship(
        "Task",
        back_populates="progress_updates",
        doc="Optional associated task",
    )

    def __init__(
        self,
        project_id: uuid.UUID,
        update_date: date | datetime,
        task_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a ProgressUpdate instance.

        Args:
            project_id: Parent project UUID.
            update_date: Date of this progress snapshot.
            task_id: Optional task UUID for task-level updates.
            percent_complete: Optional completion percentage (kwarg).
            earned_value: Optional earned value (kwarg).
            actual_cost: Optional actual cost (kwarg).
            notes: Optional progress notes (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        percent_complete = kwargs.pop("percent_complete", None)
        earned_value = kwargs.pop("earned_value", None)
        actual_cost = kwargs.pop("actual_cost", None)
        notes = kwargs.pop("notes", None)

        super().__init__(**kwargs)
        self.project_id = project_id
        self.task_id = task_id
        if isinstance(update_date, datetime):
            update_date = update_date.date()
        self.update_date = update_date
        if percent_complete is not None:
            self.percent_complete = float(percent_complete)
        if earned_value is not None:
            self.earned_value = float(earned_value)
        if actual_cost is not None:
            self.actual_cost = float(actual_cost)
        self.notes = notes

    def __repr__(self) -> str:
        """String representation of ProgressUpdate.

        Returns:
            Human-readable string with key attributes.
        """
        task_info = f", task_id={self.task_id}" if self.task_id else ""
        return f"<ProgressUpdate(id={self.id}, project_id={self.project_id}{task_info}, date={self.update_date})>"
