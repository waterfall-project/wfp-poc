# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Task model definition.

This module defines the Task model for managing work packages within
projects with EVM tracking, predecessor relationships, and multi-level WBS.
"""

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

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

CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.assignment import Assignment
    from app.models.milestone_task import MilestoneTask
    from app.models.progress_update import ProgressUpdate
    from app.models.project import Project
    from app.models.task_predecessor import TaskPredecessor
else:
    from app import db

    Model = db.Model


class Task(UUIDMixin, TimestampMixin, Model):
    """Task model for WBS work package management.

    Represents a work package in the project WBS with scheduling,
    cost tracking, and EVM calculations. Supports hierarchical
    structure via parent_id and predecessor relationships.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        parent_id: Parent task for WBS hierarchy (UUID, nullable, foreign key).
        ms_project_uid: MS Project unique ID for import reconciliation.
        wbs_code: Work Breakdown Structure code (e.g., "1.2.3").
        name: Task name (required).
        type: Task type (task, summary, milestone).
        planned_start_date: Planned start date.
        planned_finish_date: Planned finish date.
        planned_duration_minutes: Planned duration in minutes.
        actual_start_date: Actual start date (nullable).
        actual_finish_date: Actual finish date (nullable).
        percent_complete: Physical completion percentage (0-100).
        planned_cost: Planned value (PV) / Budget at Completion (BAC).
        earned_value: Earned Value (EV).
        actual_cost: Actual Cost (AC).
        remaining_cost: Estimate to Complete (ETC).
        is_critical: Critical path flag.
        status: Task status (not_started, in_progress, completed, cancelled).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "tasks"

    # Foreign Keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent project ID",
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent task ID for WBS hierarchy",
    )

    # Required Fields
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="Task name",
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="task",
        index=True,
        doc="Task type: task, summary, milestone",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_started",
        index=True,
        doc="Task status",
    )

    # Optional Fields
    ms_project_uid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project UID for import reconciliation",
    )

    wbs_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Work Breakdown Structure code",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Task description",
    )

    planned_start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="Planned start date",
    )

    planned_finish_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="Planned finish date",
    )

    planned_duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Planned duration in minutes",
    )

    actual_start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Actual start date",
    )

    actual_finish_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="Actual finish date",
    )

    percent_complete: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.0,
        doc="Physical completion percentage (0-100)",
    )

    planned_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Planned Value (PV) / Budget at Completion (BAC)",
    )

    earned_value: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Earned Value (EV)",
    )

    actual_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Actual Cost (AC)",
    )

    remaining_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate to Complete (ETC)",
    )

    is_critical: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Critical path flag",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="tasks",
        doc="Parent project",
    )

    parent: Mapped["Task | None"] = relationship(
        "Task",
        remote_side="Task.id",
        back_populates="children",
        doc="Parent task in WBS hierarchy",
    )

    children: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Child tasks in WBS hierarchy",
    )

    predecessors: Mapped[list["TaskPredecessor"]] = relationship(
        "TaskPredecessor",
        foreign_keys="TaskPredecessor.successor_id",
        back_populates="successor",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Predecessor relationships (tasks that must finish before this one)",
    )

    successors: Mapped[list["TaskPredecessor"]] = relationship(
        "TaskPredecessor",
        foreign_keys="TaskPredecessor.predecessor_id",
        back_populates="predecessor",
        doc="Successor relationships (tasks that depend on this one)",
    )

    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="task",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Resource assignments for this task",
    )

    milestone_links: Mapped[list["MilestoneTask"]] = relationship(
        "MilestoneTask",
        back_populates="task",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Milestone linkages for this task",
    )

    progress_updates: Mapped[list["ProgressUpdate"]] = relationship(
        "ProgressUpdate",
        back_populates="task",
        cascade=CASCADE_ALL_DELETE_ORPHAN,
        doc="Progress update history for this task",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "ms_project_uid",
            name="uq_tasks_project_uid",
        ),
        CheckConstraint(
            "type IN ('task', 'summary', 'milestone')",
            name="ck_tasks_type",
        ),
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed', 'cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "percent_complete >= 0 AND percent_complete <= 100",
            name="ck_tasks_percent_complete",
        ),
    )

    def __init__(self, project_id: uuid.UUID, name: str, **kwargs: Any) -> None:
        """Initialize a Task instance.

        Args:
            project_id: Parent project UUID.
            name: Task name.
            **kwargs: Additional keyword arguments passed to parent.
        """
        status = kwargs.pop("status", "not_started")
        task_type = kwargs.pop("type", "task")
        parent_id = kwargs.pop("parent_id", None)
        ms_project_uid = kwargs.pop("ms_project_uid", None)
        wbs_code = kwargs.pop("wbs_code", None)
        description = kwargs.pop("description", None)
        planned_start_date = kwargs.pop("planned_start_date", None)
        planned_finish_date = kwargs.pop("planned_finish_date", None)
        planned_duration_minutes = kwargs.pop("planned_duration_minutes", None)
        actual_start_date = kwargs.pop("actual_start_date", None)
        actual_finish_date = kwargs.pop("actual_finish_date", None)
        percent_complete = kwargs.pop("percent_complete", 0.0)
        planned_cost = kwargs.pop("planned_cost", None)
        earned_value = kwargs.pop("earned_value", None)
        actual_cost = kwargs.pop("actual_cost", None)
        remaining_cost = kwargs.pop("remaining_cost", None)
        is_critical = kwargs.pop("is_critical", False)

        super().__init__(**kwargs)
        self.project_id = project_id
        self.name = name
        self.status = status
        self.type = task_type
        self.parent_id = parent_id
        self.ms_project_uid = ms_project_uid
        self.wbs_code = wbs_code
        self.description = description
        self.planned_start_date = planned_start_date
        self.planned_finish_date = planned_finish_date
        self.planned_duration_minutes = planned_duration_minutes
        self.actual_start_date = actual_start_date
        self.actual_finish_date = actual_finish_date
        self.percent_complete = float(percent_complete)
        self.planned_cost = float(planned_cost) if planned_cost is not None else None
        self.earned_value = float(earned_value) if earned_value is not None else None
        self.actual_cost = float(actual_cost) if actual_cost is not None else None
        self.remaining_cost = (
            float(remaining_cost) if remaining_cost is not None else None
        )
        self.is_critical = is_critical

    @property
    def is_milestone(self) -> bool:
        """Check if task is a milestone.

        Returns:
            True if task type is milestone.
        """
        return self.type == "milestone"

    @property
    def is_summary(self) -> bool:
        """Check if task is a summary task.

        Returns:
            True if task type is summary.
        """
        return self.type == "summary"

    @property
    def is_deliverable(self) -> bool:
        """Check if task is a deliverable.

        For now, milestones are considered deliverables.
        Can be extended with dedicated field if needed.

        Returns:
            True if task is a milestone.
        """
        return self.type == "milestone"

    def __repr__(self) -> str:
        """String representation of Task.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Task(id={self.id}, name='{self.name}', status='{self.status}')>"

    @staticmethod
    def _normalize_datetime(value: datetime | date | None) -> datetime | None:
        """Normalize datelike inputs to naive UTC datetimes."""
        if value is None:
            return None

        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())

        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)

        return value

    @validates(
        "planned_start_date",
        "planned_finish_date",
        "actual_start_date",
        "actual_finish_date",
    )
    def _validate_datetime_field(
        self, key: str, value: datetime | date | None
    ) -> datetime | None:
        """Ensure task datetime fields are stored as naive UTC values."""
        return self._normalize_datetime(value)
