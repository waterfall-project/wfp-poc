# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Assignment model definition.

This module defines the Assignment model for managing resource allocations
to specific tasks with planned work and actual effort tracking.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.project import Project
    from app.models.resource import Resource
    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class Assignment(UUIDMixin, TimestampMixin, Model):
    """Assignment model for resource-task allocation.

    Represents the assignment of a resource to a specific task,
    including planned work, actual work, and cost allocation.

    Attributes:
        id: Unique identifier (UUID, primary key).
        task_id: Task identifier (UUID, required, foreign key).
        resource_id: Resource identifier (UUID, required, foreign key).
        project_id: Project identifier for denormalization (UUID, required, foreign key).
        ms_project_uid: Optional MS Project assignment UID for reconciliation.
        percent_allocation: Allocation percentage (0-100).
        planned_work_minutes: Planned work effort in minutes.
        actual_work_minutes: Actual work effort in minutes.
        planned_cost: Planned cost for this assignment.
        actual_cost: Actual cost incurred for this assignment.
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "assignments"

    # Foreign Keys
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Task ID",
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Resource ID",
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Project ID (denormalized for query performance)",
    )

    # Optional Fields
    ms_project_uid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project assignment UID",
    )

    percent_allocation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        doc="Allocation percentage (0-100)",
    )

    planned_work_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Planned work effort in minutes",
    )

    actual_work_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Actual work effort in minutes",
    )

    planned_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Planned cost for this assignment",
    )

    actual_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        default=0,
        doc="Actual cost incurred for this assignment",
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="assignments",
        doc="Associated task",
    )

    resource: Mapped["Resource"] = relationship(
        "Resource",
        back_populates="assignments",
        doc="Assigned resource",
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="assignments",
        doc="Parent project (denormalized)",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "resource_id",
            name="uq_assignments_task_resource",
        ),
        CheckConstraint(
            "percent_allocation >= 0",
            name="ck_assignment_percent_allocation_min",
        ),
        CheckConstraint(
            "percent_allocation <= 100",
            name="ck_assignment_percent_allocation_max",
        ),
    )

    def __init__(
        self,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        resource_id: uuid.UUID,
        percent_allocation: int = 100,
        planned_work_minutes: int | None = None,
        actual_work_minutes: int | None = None,
        planned_cost: float | int | Decimal | None = None,
        actual_cost: float | int | Decimal | None = 0,
        ms_project_uid: int | None = None,
        **kwargs,
    ) -> None:
        """Initialize an Assignment instance.

        Args:
            project_id: Project UUID for denormalization.
            task_id: Task UUID for the assignment.
            resource_id: Resource UUID for the assignment.
            percent_allocation: Allocation percentage (0-100).
            planned_work_minutes: Planned work in minutes.
            actual_work_minutes: Actual work in minutes.
            planned_cost: Planned cost for the assignment.
            actual_cost: Actual cost incurred for the assignment.
            ms_project_uid: Optional MS Project assignment UID.
            **kwargs: Additional keyword arguments passed to parent.
        """
        super().__init__(**kwargs)
        self.project_id = project_id
        self.task_id = task_id
        self.resource_id = resource_id
        self.percent_allocation = percent_allocation
        self.planned_work_minutes = planned_work_minutes
        self.actual_work_minutes = actual_work_minutes

        def _normalize_decimal(value: float | int | Decimal | None) -> Decimal | None:
            if value is None:
                return None
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))

        self.planned_cost = _normalize_decimal(planned_cost)
        self.actual_cost = _normalize_decimal(actual_cost)
        self.ms_project_uid = ms_project_uid

    def __repr__(self) -> str:
        """String representation of Assignment.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Assignment(id={self.id}, task_id={self.task_id}, resource_id={self.resource_id})>"
