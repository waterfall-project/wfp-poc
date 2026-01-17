# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Expense model definition.

This module defines the Expense model for tracking project costs
beyond resource assignments, including materials and fixed costs.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.milestone import Milestone
    from app.models.project import Project
    from app.models.resource import Resource
else:
    from app import db

    Model = db.Model


class Expense(UUIDMixin, TimestampMixin, Model):
    """Expense model for project cost tracking.

    Represents an expense item in the project, tracking costs
    beyond resource labor assignments (materials, fixed costs, etc.).

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        milestone_id: Optional milestone allocation (UUID, nullable, foreign key).
        resource_id: Optional associated resource (UUID, nullable, foreign key).
        category: Expense category (material, fixed, other).
        description: Expense description (required).
        planned_cost: Planned expense amount.
        actual_cost: Actual expense amount (nullable).
        expense_date: Date of expense incurrence.
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "expenses"

    # Foreign Keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent project ID",
    )

    milestone_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("milestones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Allocated milestone ID (auto-assigned based on expense date)",
    )

    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional associated resource ID",
    )

    # Required Fields
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="other",
        index=True,
        doc="Expense category: material, fixed, other",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Expense description",
    )

    # Optional Fields
    planned_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Planned expense amount",
    )

    actual_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Actual expense amount",
    )

    expense_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        doc="Date of expense incurrence",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="expenses",
        doc="Parent project",
    )

    milestone: Mapped["Milestone | None"] = relationship(
        "Milestone",
        back_populates="expenses",
        doc="Allocated milestone",
    )

    resource: Mapped["Resource | None"] = relationship(
        "Resource",
        back_populates="expenses",
        doc="Optional associated resource",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "category IN ('material', 'fixed', 'other')",
            name="ck_expenses_category",
        ),
    )

    def __init__(
        self,
        project_id: uuid.UUID,
        description: str,
        category: str = "other",
        **kwargs: Any,
    ) -> None:
        """Initialize an Expense instance.

        Args:
            project_id: Parent project UUID.
            description: Expense description.
            category: Expense category.
            milestone_id: Optional milestone UUID (kwarg).
            resource_id: Optional resource UUID (kwarg).
            planned_cost: Optional planned cost (kwarg).
            actual_cost: Optional actual cost (kwarg).
            expense_date: Optional expense date (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        milestone_id = kwargs.pop("milestone_id", None)
        resource_id = kwargs.pop("resource_id", None)
        planned_cost = kwargs.pop("planned_cost", None)
        actual_cost = kwargs.pop("actual_cost", None)
        expense_date = kwargs.pop("expense_date", None)

        super().__init__(**kwargs)
        self.project_id = project_id
        self.category = category
        self.description = description
        self.milestone_id = milestone_id
        self.resource_id = resource_id
        self.planned_cost = float(planned_cost) if planned_cost is not None else None
        self.actual_cost = float(actual_cost) if actual_cost is not None else None
        self.expense_date = expense_date

    def __repr__(self) -> str:
        """String representation of Expense.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Expense(id={self.id}, category='{self.category}', description='{self.description[:30]}')>"
