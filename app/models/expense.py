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
beyond resource assignments, aligned with the OpenAPI contract.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
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
        date: Expense date (required).
        amount: Expense amount (required).
        category: Expense category (labor, procurement, subcontracting, overhead).
        description: Optional expense description.
        reference_number: Optional ERP reference number.
        purchase_document: Optional ERP purchase document.
        fiscal_year: Optional ERP fiscal year.
        period: Optional ERP period (1-12).
        otp_element: Optional ERP OTP element.
        accounting_nature: Optional ERP accounting nature.
        vendor_name: Optional ERP vendor/resource name.
        origin_group: Optional ERP origin group.
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
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Expense date (ERP document date)",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Expense amount",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="procurement",
        index=True,
        doc="Expense category: labor, procurement, subcontracting, overhead",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Expense description",
    )

    # Optional ERP Fields
    reference_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="ERP reference number",
    )

    purchase_document: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="ERP purchase document",
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="ERP fiscal year",
    )

    period: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="ERP period (month)",
    )

    otp_element: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="ERP OTP element",
    )

    accounting_nature: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="ERP accounting nature",
    )

    vendor_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Vendor or resource name",
    )

    origin_group: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="ERP origin group",
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
            "category IN ('labor', 'procurement', 'subcontracting', 'overhead')",
            name="ck_expenses_category",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_expenses_amount_non_negative",
        ),
        UniqueConstraint(
            "reference_number",
            "date",
            "amount",
            name="uq_expenses_reference_date_amount",
        ),
        CheckConstraint(
            "period IS NULL OR (period >= 1 AND period <= 12)",
            name="ck_expenses_period_range",
        ),
    )

    def __init__(
        self,
        project_id: uuid.UUID,
        date: datetime,
        amount: Decimal,
        category: str = "procurement",
        description: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize an Expense instance.

        Args:
            project_id: Parent project UUID.
            date: Expense date.
            amount: Expense amount.
            category: Expense category.
            description: Optional description.
            milestone_id: Optional milestone UUID (kwarg).
            resource_id: Optional resource UUID (kwarg).
            reference_number: Optional ERP reference number (kwarg).
            purchase_document: Optional ERP purchase document (kwarg).
            fiscal_year: Optional ERP fiscal year (kwarg).
            period: Optional ERP period (kwarg).
            otp_element: Optional ERP OTP element (kwarg).
            accounting_nature: Optional ERP accounting nature (kwarg).
            vendor_name: Optional ERP vendor name (kwarg).
            origin_group: Optional ERP origin group (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        milestone_id = kwargs.pop("milestone_id", None)
        resource_id = kwargs.pop("resource_id", None)
        reference_number = kwargs.pop("reference_number", None)
        purchase_document = kwargs.pop("purchase_document", None)
        fiscal_year = kwargs.pop("fiscal_year", None)
        period = kwargs.pop("period", None)
        otp_element = kwargs.pop("otp_element", None)
        accounting_nature = kwargs.pop("accounting_nature", None)
        vendor_name = kwargs.pop("vendor_name", None)
        origin_group = kwargs.pop("origin_group", None)

        super().__init__(**kwargs)
        self.project_id = project_id
        self.category = category
        self.date = date
        self.amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        self.description = description
        self.milestone_id = milestone_id
        self.resource_id = resource_id
        self.reference_number = reference_number
        self.purchase_document = purchase_document
        self.fiscal_year = fiscal_year
        self.period = period
        self.otp_element = otp_element
        self.accounting_nature = accounting_nature
        self.vendor_name = vendor_name
        self.origin_group = origin_group

    def __repr__(self) -> str:
        """String representation of Expense.

        Returns:
            Human-readable string with key attributes.
        """
        return (
            f"<Expense(id={self.id}, category='{self.category}', amount={self.amount})>"
        )
