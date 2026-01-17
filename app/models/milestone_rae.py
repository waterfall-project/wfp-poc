# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Milestone RAE (Remaining Amount Estimate) model definition.

This module defines the MilestoneRAE model for tracking historical RAE values
for milestones. RAE represents the estimated remaining cost to complete a milestone,
used for physical EV calculation.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, JSONB, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.milestone import Milestone
else:
    from app import db

    Model = db.Model


class MilestoneRAE(UUIDMixin, TimestampMixin, Model):
    """Milestone RAE (Remaining Amount Estimate) model.

    Stores historical RAE entries for milestones, tracking the estimated
    remaining cost to complete each milestone over time. Used for calculating
    physical Earned Value (EV) based on the formula:
    EV_physical = BAC - RAE.

    Each entry records a point-in-time RAE estimate with optional task-level
    breakdown and explanation.

    Attributes:
        id: Unique identifier (UUID, primary key).
        milestone_id: Parent milestone identifier (UUID, required, foreign key).
        date: Date of RAE measurement (required, typically month-end).
        amount: Estimated remaining cost to complete the milestone (required).
        comment: Optional explanation for this RAE estimate (max 500 chars).
        details: Optional task-level breakdown used for bottom-up calculation (JSONB).
        updated_by: User ID who recorded this RAE (from JWT claims, required).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "milestone_rae"

    # Foreign Keys
    milestone_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("milestones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent milestone ID",
    )

    # Required Fields
    date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        doc="Date of RAE measurement (typically month-end)",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        doc="Estimated remaining cost to complete the milestone",
    )

    updated_by: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        nullable=False,
        index=True,
        doc="User ID who recorded this RAE (from JWT claims)",
    )

    # Optional Fields
    comment: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional explanation for this RAE estimate",
    )

    details: Mapped[dict | None] = mapped_column(
        JSONB(),
        nullable=True,
        doc="Optional task-level breakdown for bottom-up calculation (JSONB)",
    )

    # Relationships
    milestone: Mapped["Milestone"] = relationship(
        "Milestone",
        back_populates="rae_history",
        doc="Parent milestone",
    )

    # Indexes
    __table_args__ = (
        Index("idx_milestone_rae_milestone_date", "milestone_id", "date"),
        Index("idx_milestone_rae_date", "date"),
    )

    def __init__(
        self,
        milestone_id: uuid.UUID,
        date: datetime,
        amount: Decimal | float,
        updated_by: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize a MilestoneRAE instance.

        Args:
            milestone_id: Parent milestone UUID.
            date: Date of RAE measurement.
            amount: Estimated remaining cost.
            updated_by: User ID who recorded this RAE.
            comment: Optional explanation (kwarg).
            details: Optional task-level breakdown (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        comment = kwargs.pop("comment", None)
        details = kwargs.pop("details", None)

        super().__init__(**kwargs)
        self.milestone_id = milestone_id
        self.date = date
        self.amount = (
            Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
        )
        self.updated_by = updated_by
        self.comment = comment
        self.details = details

    def __repr__(self) -> str:
        """String representation of MilestoneRAE.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<MilestoneRAE(id={self.id}, milestone_id={self.milestone_id}, date={self.date}, amount={self.amount})>"
