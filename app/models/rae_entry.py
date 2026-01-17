# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""RAE entry model definition.

This module defines the RAEEntry model for tracking Risks, Assumptions,
and Exceptions associated with project tasks.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, JSONB, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.task import Task
else:
    from app import db

    Model = db.Model


class RAEEntry(UUIDMixin, TimestampMixin, Model):
    """RAE entry model for risk, assumption, and exception tracking.

    Represents a Risk, Assumption, or Exception entry linked to a task,
    with categorization, severity, status tracking, and flexible details storage.

    Attributes:
        id: Unique identifier (UUID, primary key).
        task_id: Parent task identifier (UUID, required, foreign key).
        type: Entry type (risk, assumption, exception).
        category: Entry category (technical, financial, schedule, resource, quality, other).
        severity: Severity level (low, medium, high, critical).
        status: Current status (open, mitigated, resolved, closed).
        description: Entry description (required).
        mitigation: Optional mitigation plan or actions taken.
        identified_date: Date when entry was identified.
        resolution_date: Date when entry was resolved (nullable).
        details: Additional flexible JSONB field for custom attributes.
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "rae_entries"

    # Foreign Keys
    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent task ID",
    )

    # Required Fields
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Entry type: risk, assumption, exception",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
        index=True,
        doc="Entry category: technical, financial, schedule, resource, quality, other",
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        doc="Severity level: low, medium, high, critical",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        index=True,
        doc="Current status: open, mitigated, resolved, closed",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Entry description",
    )

    # Optional Fields
    mitigation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Mitigation plan or actions taken",
    )

    identified_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        doc="Date when entry was identified",
    )

    resolution_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date when entry was resolved",
    )

    details: Mapped[dict | None] = mapped_column(
        JSONB(),
        nullable=True,
        doc="Additional flexible attributes (JSONB)",
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="rae_entries",
        doc="Parent task",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('risk', 'assumption', 'exception')",
            name="ck_rae_entries_type",
        ),
        CheckConstraint(
            "category IN ('technical', 'financial', 'schedule', 'resource', 'quality', 'other')",
            name="ck_rae_entries_category",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_rae_entries_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'mitigated', 'resolved', 'closed')",
            name="ck_rae_entries_status",
        ),
    )

    def __init__(
        self,
        task_id: uuid.UUID,
        type: str,
        description: str,
        category: str = "other",
        severity: str = "medium",
        status: str = "open",
        **kwargs: Any,
    ) -> None:
        """Initialize an RAEEntry instance.

        Args:
            task_id: Parent task UUID.
            type: Entry type (risk, assumption, exception).
            description: Entry description.
            category: Entry category.
            severity: Severity level.
            status: Current status.
            mitigation: Optional mitigation plan (kwarg).
            identified_date: Optional identified date (kwarg).
            resolution_date: Optional resolution date (kwarg).
            details: Optional details JSON (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        mitigation = kwargs.pop("mitigation", None)
        identified_date: date | datetime | None = kwargs.pop("identified_date", None)
        resolution_date: date | datetime | None = kwargs.pop("resolution_date", None)
        details = kwargs.pop("details", None)

        super().__init__(**kwargs)
        self.task_id = task_id
        self.type = type
        self.category = category
        self.severity = severity
        self.status = status
        self.description = description
        self.mitigation = mitigation
        if isinstance(identified_date, datetime):
            identified_date = identified_date.date()
        if isinstance(resolution_date, datetime):
            resolution_date = resolution_date.date()
        self.identified_date = identified_date
        self.resolution_date = resolution_date
        self.details = details

    def __repr__(self) -> str:
        """String representation of RAEEntry.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<RAEEntry(id={self.id}, type='{self.type}', severity='{self.severity}', status='{self.status}')>"
