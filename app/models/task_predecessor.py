# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Task predecessor relationship model definition.

This module defines the TaskPredecessor model for managing task dependencies
and scheduling relationships in the project network diagram.
"""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class TaskPredecessor(UUIDMixin, TimestampMixin, Model):
    """Task predecessor relationship model.

    Represents a dependency between two tasks in the project network.
    Defines the type of relationship (FS, SS, FF, SF) and optional lag time.

    Attributes:
        id: Unique identifier (UUID, primary key).
        predecessor_id: Task that must complete first (UUID, required, foreign key).
        successor_id: Task that depends on predecessor (UUID, required, foreign key).
        type: Relationship type (FS, SS, FF, SF).
        lag_minutes: Lag time in minutes (positive = delay, negative = lead).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "task_predecessors"

    # Foreign Keys
    predecessor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Task that must complete first",
    )

    successor_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Task that depends on predecessor",
    )

    # Required Fields
    type: Mapped[str] = mapped_column(
        "type",
        nullable=False,
        default="FS",
        doc="Relationship type: FS (Finish-to-Start), SS (Start-to-Start), FF (Finish-to-Finish), SF (Start-to-Finish)",
    )

    # Optional Fields
    lag_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Lag time in minutes (positive = delay, negative = lead)",
    )

    # Relationships
    predecessor: Mapped["Task"] = relationship(
        "Task",
        foreign_keys=[predecessor_id],
        back_populates="successors",
        doc="Predecessor task (must finish first)",
    )

    successor: Mapped["Task"] = relationship(
        "Task",
        foreign_keys=[successor_id],
        back_populates="predecessors",
        doc="Successor task (depends on predecessor)",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "predecessor_id",
            "successor_id",
            name="uq_task_predecessors_pair",
        ),
        CheckConstraint(
            "type IN ('FS', 'SS', 'FF', 'SF')",
            name="ck_task_predecessors_type",
        ),
        CheckConstraint(
            "predecessor_id != successor_id",
            name="ck_task_predecessors_no_self_reference",
        ),
    )

    def __init__(
        self,
        predecessor_id: uuid.UUID,
        successor_id: uuid.UUID,
        type: str = "FS",
        lag_minutes: int = 0,
        **kwargs: Any,
    ) -> None:
        """Initialize a TaskPredecessor instance.

        Args:
            predecessor_id: Task UUID that must complete first.
            successor_id: Task UUID that depends on predecessor.
            type: Relationship type (FS, SS, FF, SF).
            lag_minutes: Lag time in minutes (positive = delay, negative = lead).
            **kwargs: Additional keyword arguments passed to parent.
        """
        super().__init__(**kwargs)
        self.predecessor_id = predecessor_id
        self.successor_id = successor_id
        self.type = type
        self.lag_minutes = lag_minutes

    def __repr__(self) -> str:
        """String representation of TaskPredecessor.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<TaskPredecessor(predecessor_id={self.predecessor_id}, successor_id={self.successor_id}, type='{self.type}')>"
