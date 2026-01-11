# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Resource model definition.

This module defines the Resource model for managing labor, material,
and cost resources across projects with company-level scoping.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.assignment import Assignment
    from app.models.expense import Expense
else:
    from app import db

    Model = db.Model


class Resource(UUIDMixin, TimestampMixin, Model):
    """Resource model for project resource management.

    Represents a human, material, or cost resource that can be assigned
    to project tasks. Resources are company-scoped and shared across projects.

    Attributes:
        id: Unique identifier (UUID, primary key).
        company_id: Company identifier for multi-tenancy (UUID, required).
        ms_project_uid: MS Project unique ID for import reconciliation.
        name: Resource name (required, unique per company).
        type: Resource type (labor, material, cost).
        standard_rate: Standard hourly/unit rate.
        overtime_rate: Overtime hourly rate (for labor).
        email: Email address (for labor resources).
        is_active: Active status flag (default True).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "resources"

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
        doc="Resource name",
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="labor",
        index=True,
        doc="Resource type: labor, material, cost",
    )

    # Optional Fields
    ms_project_uid: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="MS Project UID for import reconciliation",
    )

    standard_rate: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Standard hourly/unit rate",
    )

    overtime_rate: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Overtime rate (for labor)",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Email address (for labor resources)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        doc="Active status (soft delete flag)",
    )

    # Relationships
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="resource",
        doc="Task assignments for this resource",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="resource",
        doc="Expenses associated with this resource",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_resources_company_name",
        ),
        CheckConstraint(
            "type IN ('labor', 'material', 'cost')",
            name="ck_resources_type",
        ),
    )

    def __repr__(self) -> str:
        """String representation of Resource.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<Resource(id={self.id}, name='{self.name}', type='{self.type}')>"
