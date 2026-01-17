# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""EVM snapshot model definition.

This module defines the EVMSnapshot model for storing periodic EVM
calculations at specific status dates for project tracking and forecasting.
"""

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.types import GUID, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from app.models.project import Project
else:
    from app import db

    Model = db.Model


class EVMSnapshot(UUIDMixin, TimestampMixin, Model):
    """EVM snapshot model for historical EVM metrics.

    Stores periodic snapshots of EVM calculations at specific status dates,
    capturing all key EVM indicators for project performance analysis and forecasting.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        status_date: Date of this EVM snapshot (required).
        planned_value: Planned Value (PV) / Budgeted Cost of Work Scheduled (BCWS).
        earned_value: Earned Value (EV) / Budgeted Cost of Work Performed (BCWP).
        actual_cost: Actual Cost (AC) / Actual Cost of Work Performed (ACWP).
        budget_at_completion: Budget at Completion (BAC).
        estimate_at_completion: Estimate at Completion (EAC).
        estimate_to_complete: Estimate to Complete (ETC).
        variance_at_completion: Variance at Completion (VAC).
        schedule_variance: Schedule Variance (SV = EV - PV).
        cost_variance: Cost Variance (CV = EV - AC).
        schedule_performance_index: Schedule Performance Index (SPI = EV / PV).
        cost_performance_index: Cost Performance Index (CPI = EV / AC).
        to_complete_performance_index: To Complete Performance Index (TCPI).
        created_at: Timestamp of creation (auto-generated).
        updated_at: Timestamp of last update (auto-updated).
    """

    __tablename__ = "evm_snapshots"

    # Foreign Keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent project ID",
    )

    # Required Fields
    status_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        doc="Date of this EVM snapshot",
    )

    # EVM Core Metrics
    planned_value: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Planned Value (PV) / BCWS",
    )

    earned_value: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Earned Value (EV) / BCWP",
    )

    actual_cost: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Actual Cost (AC) / ACWP",
    )

    budget_at_completion: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Budget at Completion (BAC)",
    )

    estimate_at_completion: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate at Completion (EAC)",
    )

    estimate_to_complete: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate to Complete (ETC)",
    )

    variance_at_completion: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Variance at Completion (VAC)",
    )

    # EVM Variances
    schedule_variance: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Schedule Variance (SV = EV - PV)",
    )

    cost_variance: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Cost Variance (CV = EV - AC)",
    )

    # EVM Performance Indices
    schedule_performance_index: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Schedule Performance Index (SPI = EV / PV)",
    )

    cost_performance_index: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Cost Performance Index (CPI = EV / AC)",
    )

    to_complete_performance_index: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="To Complete Performance Index (TCPI)",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="evm_snapshots",
        doc="Parent project",
    )

    def __init__(
        self,
        project_id: uuid.UUID,
        status_date: date,
        **kwargs: Any,
    ) -> None:
        """Initialize an EVMSnapshot instance.

        Args:
            project_id: Parent project UUID.
            status_date: Snapshot status date.
            planned_value: Planned Value (PV) / BCWS (kwarg).
            earned_value: Earned Value (EV) / BCWP (kwarg).
            actual_cost: Actual Cost (AC) / ACWP (kwarg).
            budget_at_completion: Budget at Completion (BAC) (kwarg).
            estimate_at_completion: Estimate at Completion (EAC) (kwarg).
            estimate_to_complete: Estimate to Complete (ETC) (kwarg).
            variance_at_completion: Variance at Completion (VAC) (kwarg).
            schedule_variance: Schedule Variance (SV) (kwarg).
            cost_variance: Cost Variance (CV) (kwarg).
            schedule_performance_index: Schedule Performance Index (SPI) (kwarg).
            cost_performance_index: Cost Performance Index (CPI) (kwarg).
            to_complete_performance_index: To Complete Performance Index (TCPI) (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        planned_value = kwargs.pop("planned_value", None)
        earned_value = kwargs.pop("earned_value", None)
        actual_cost = kwargs.pop("actual_cost", None)
        budget_at_completion = kwargs.pop("budget_at_completion", None)
        estimate_at_completion = kwargs.pop("estimate_at_completion", None)
        estimate_to_complete = kwargs.pop("estimate_to_complete", None)
        variance_at_completion = kwargs.pop("variance_at_completion", None)
        schedule_variance = kwargs.pop("schedule_variance", None)
        cost_variance = kwargs.pop("cost_variance", None)
        schedule_performance_index = kwargs.pop("schedule_performance_index", None)
        cost_performance_index = kwargs.pop("cost_performance_index", None)
        to_complete_performance_index = kwargs.pop(
            "to_complete_performance_index", None
        )

        super().__init__(**kwargs)
        self.project_id = project_id
        self.status_date = status_date
        self.planned_value = planned_value
        self.earned_value = earned_value
        self.actual_cost = actual_cost
        self.budget_at_completion = budget_at_completion
        self.estimate_at_completion = estimate_at_completion
        self.estimate_to_complete = estimate_to_complete
        self.variance_at_completion = variance_at_completion
        self.schedule_variance = schedule_variance
        self.cost_variance = cost_variance
        self.schedule_performance_index = schedule_performance_index
        self.cost_performance_index = cost_performance_index
        self.to_complete_performance_index = to_complete_performance_index

    def __repr__(self) -> str:
        """String representation of EVMSnapshot.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<EVMSnapshot(id={self.id}, project_id={self.project_id}, status_date={self.status_date})>"
