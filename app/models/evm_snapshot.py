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
Stores both physical (RAE-based) and milestone-based EV calculations.
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
    Supports both physical (RAE-based) and milestone-based EV calculation methods.

    Attributes:
        id: Unique identifier (UUID, primary key).
        project_id: Parent project identifier (UUID, required, foreign key).
        snapshot_date: Date of this EVM snapshot (required).
        bac: Budget at Completion.
        pv: Planned Value (PV) / Budgeted Cost of Work Scheduled (BCWS).
        ac: Actual Cost (AC) / Actual Cost of Work Performed (ACWP).
        ev_physical: Earned Value using physical progress (RAE-based) method.
        ev_milestone: Earned Value using milestone completion method.
        cv_physical: Cost Variance (EV_physical - AC).
        sv_physical: Schedule Variance (EV_physical - PV).
        cpi_physical: Cost Performance Index (EV_physical / AC).
        spi_physical: Schedule Performance Index (EV_physical / PV).
        eac_cpi_physical: Estimate at Completion using CPI method (BAC / CPI).
        eac_cpispi_physical: Estimate at Completion using CPI*SPI method.
        eac_plan_physical: Estimate at Completion using plan-based method.
        etc_physical: Estimate to Complete (EAC - AC).
        vac_physical: Variance at Completion (BAC - EAC).
        tcpi_bac: To Complete Performance Index based on BAC.
        percent_complete: Overall project completion percentage.
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
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        doc="Date of this EVM snapshot",
    )

    # EVM Core Metrics
    bac: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Budget at Completion (BAC)",
    )

    pv: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Planned Value (PV) / BCWS",
    )

    ac: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Actual Cost (AC) / ACWP",
    )

    ev_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Earned Value using physical progress (RAE-based) method",
    )

    ev_milestone: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Earned Value using milestone completion method",
    )

    # EVM Variances (Physical Method)
    cv_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Cost Variance (CV = EV_physical - AC)",
    )

    sv_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Schedule Variance (SV = EV_physical - PV)",
    )

    # EVM Performance Indices (Physical Method)
    cpi_physical: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Cost Performance Index (CPI = EV_physical / AC)",
    )

    spi_physical: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="Schedule Performance Index (SPI = EV_physical / PV)",
    )

    # EVM Forecasts (Physical Method)
    eac_cpi_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate at Completion using CPI method (BAC / CPI)",
    )

    eac_cpispi_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate at Completion using CPI*SPI method",
    )

    eac_plan_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate at Completion using plan-based method",
    )

    etc_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Estimate to Complete (ETC = EAC - AC)",
    )

    vac_physical: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Variance at Completion (VAC = BAC - EAC)",
    )

    tcpi_bac: Mapped[float | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        doc="To Complete Performance Index based on BAC",
    )

    percent_complete: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Overall project completion percentage (0-100)",
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
        snapshot_date: date,
        **kwargs: Any,
    ) -> None:
        """Initialize an EVMSnapshot instance.

        Args:
            project_id: Parent project UUID.
            snapshot_date: Snapshot status date.
            bac: Budget at Completion (BAC) (kwarg).
            pv: Planned Value (PV) / BCWS (kwarg).
            ac: Actual Cost (AC) / ACWP (kwarg).
            ev_physical: Earned Value using physical method (kwarg).
            ev_milestone: Earned Value using milestone method (kwarg).
            cv_physical: Cost Variance (physical method) (kwarg).
            sv_physical: Schedule Variance (physical method) (kwarg).
            cpi_physical: Cost Performance Index (physical method) (kwarg).
            spi_physical: Schedule Performance Index (physical method) (kwarg).
            eac_cpi_physical: EAC using CPI method (kwarg).
            eac_cpispi_physical: EAC using CPI*SPI method (kwarg).
            eac_plan_physical: EAC using plan-based method (kwarg).
            etc_physical: Estimate to Complete (kwarg).
            vac_physical: Variance at Completion (kwarg).
            tcpi_bac: To Complete Performance Index (kwarg).
            percent_complete: Overall completion percentage (kwarg).
            **kwargs: Additional keyword arguments passed to parent.
        """
        bac = kwargs.pop("bac", None)
        pv = kwargs.pop("pv", None)
        ac = kwargs.pop("ac", None)
        ev_physical = kwargs.pop("ev_physical", None)
        ev_milestone = kwargs.pop("ev_milestone", None)
        cv_physical = kwargs.pop("cv_physical", None)
        sv_physical = kwargs.pop("sv_physical", None)
        cpi_physical = kwargs.pop("cpi_physical", None)
        spi_physical = kwargs.pop("spi_physical", None)
        eac_cpi_physical = kwargs.pop("eac_cpi_physical", None)
        eac_cpispi_physical = kwargs.pop("eac_cpispi_physical", None)
        eac_plan_physical = kwargs.pop("eac_plan_physical", None)
        etc_physical = kwargs.pop("etc_physical", None)
        vac_physical = kwargs.pop("vac_physical", None)
        tcpi_bac = kwargs.pop("tcpi_bac", None)
        percent_complete = kwargs.pop("percent_complete", None)

        super().__init__(**kwargs)
        self.project_id = project_id
        self.snapshot_date = snapshot_date
        self.bac = bac
        self.pv = pv
        self.ac = ac
        self.ev_physical = ev_physical
        self.ev_milestone = ev_milestone
        self.cv_physical = cv_physical
        self.sv_physical = sv_physical
        self.cpi_physical = cpi_physical
        self.spi_physical = spi_physical
        self.eac_cpi_physical = eac_cpi_physical
        self.eac_cpispi_physical = eac_cpispi_physical
        self.eac_plan_physical = eac_plan_physical
        self.etc_physical = etc_physical
        self.vac_physical = vac_physical
        self.tcpi_bac = tcpi_bac
        self.percent_complete = percent_complete

    def __repr__(self) -> str:
        """String representation of EVMSnapshot.

        Returns:
            Human-readable string with key attributes.
        """
        return f"<EVMSnapshot(id={self.id}, project_id={self.project_id}, snapshot_date={self.snapshot_date})>"
