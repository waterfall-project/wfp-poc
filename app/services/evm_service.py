# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""EVM service for calculation logic.

Provides EVM indicator, time-series, and forecast calculations using
project tasks, milestones, expenses, and RAE history.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.models.expense import Expense
from app.models.milestone import Milestone
from app.models.milestone_rae import MilestoneRAE
from app.models.task import Task

if TYPE_CHECKING:
    from flask_sqlalchemy.session import Session as FlaskSession
    from sqlalchemy.orm import Session
    from sqlalchemy.orm.scoping import scoped_session

    from app.models.project import Project


class EVMService:
    """Service class for EVM calculations.

    Handles calculation of PV, AC, EV, and derived metrics for
    indicators, time-series, and forecast endpoints.

    Attributes:
        db_session: SQLAlchemy session used for database queries.
    """

    def __init__(
        self,
        db_session: Session
        | FlaskSession
        | scoped_session[Session]
        | scoped_session[FlaskSession],
    ) -> None:
        """Initialize EVMService with database session.

        Args:
            db_session: SQLAlchemy session for database operations.
        """
        self.db_session = db_session

    def calculate_indicators(
        self,
        project: Project,
        as_of_date: datetime,
        ev_method: str,
    ) -> dict[str, Any]:
        """Calculate EVM indicators for a project.

        Args:
            project: Project entity.
            as_of_date: Reference date for calculations.
            ev_method: EV calculation method (physical, milestone, both).

        Returns:
            Dictionary of EVM indicator values.
        """
        tasks = self._get_tasks(project.id)
        milestones = self._get_milestones(project.id)
        expenses = self._get_expenses(project.id)
        rae_entries = self._get_rae_entries(project.id, as_of_date)

        bac = self._calculate_bac(tasks, project)
        pv = self._calculate_pv(tasks, as_of_date)
        ac = self._calculate_ac(expenses, as_of_date)

        rae_total, has_rae = self._calculate_total_rae(
            milestones, rae_entries, as_of_date
        )
        if not has_rae and bac is not None:
            rae_total = bac

        ev_physical = None
        if ev_method in {"physical", "both"}:
            ev_physical = self._calculate_ev_physical(bac, ac, rae_total)

        ev_milestone = None
        if ev_method in {"milestone", "both"}:
            ev_milestone = self._calculate_ev_milestone(bac, milestones, as_of_date)

        cv_physical = self._safe_subtract(ev_physical, ac)
        sv_physical = self._safe_subtract(ev_physical, pv)
        cpi_physical = self._safe_divide(ev_physical, ac)
        spi_physical = self._safe_divide(ev_physical, pv)

        eac_cpi_physical = self._calculate_eac_cpi(bac, cpi_physical)
        etc_physical = self._safe_subtract(eac_cpi_physical, ac)
        vac_physical = self._safe_subtract(bac, eac_cpi_physical)

        return {
            "project_id": project.id,
            "as_of_date": as_of_date,
            "bac": bac,
            "pv": pv,
            "ac": ac,
            "ev_physical": ev_physical,
            "ev_milestone": ev_milestone,
            "cv_physical": cv_physical,
            "sv_physical": sv_physical,
            "cpi_physical": cpi_physical,
            "spi_physical": spi_physical,
            "eac_cpi_physical": eac_cpi_physical,
            "etc_physical": etc_physical,
            "vac_physical": vac_physical,
        }

    def get_time_series(
        self,
        project: Project,
        start_date: datetime,
        end_date: datetime,
        granularity: str,
        ev_method: str,
        cumulative: bool,
    ) -> dict[str, Any]:
        """Build EVM time series data for a project.

        Args:
            project: Project entity.
            start_date: Start of time series range.
            end_date: End of time series range.
            granularity: Granularity (month supported in POC).
            ev_method: EV calculation method (physical or milestone).
            cumulative: Whether values are cumulative.

        Returns:
            Dictionary with time series data arrays.
        """
        if granularity != "month":
            raise ValueError("Only monthly granularity is supported in POC")

        tasks = self._get_tasks(project.id)
        milestones = self._get_milestones(project.id)
        expenses = self._get_expenses(project.id)
        rae_entries = self._get_rae_entries(project.id, end_date)

        dates = self._build_month_end_dates(start_date, end_date)
        pv_series: list[Decimal] = []
        ac_series: list[Decimal] = []
        ev_series: list[Decimal] = []

        for date_point in dates:
            bac = self._calculate_bac(tasks, project)
            pv = self._calculate_pv(tasks, date_point)
            ac = self._calculate_ac(expenses, date_point)

            rae_total, has_rae = self._calculate_total_rae(
                milestones, rae_entries, date_point
            )
            if not has_rae and bac is not None:
                rae_total = bac

            if ev_method == "milestone":
                ev = self._calculate_ev_milestone(bac, milestones, date_point)
            else:
                ev = self._calculate_ev_physical(bac, ac, rae_total)

            pv_series.append(pv or Decimal("0"))
            ac_series.append(ac or Decimal("0"))
            ev_series.append(ev or Decimal("0"))

        if not cumulative:
            pv_series = self._to_period_series(pv_series)
            ac_series = self._to_period_series(ac_series)
            ev_series = self._to_period_series(ev_series)

        return {
            "project_id": project.id,
            "start_date": start_date,
            "end_date": end_date,
            "granularity": "monthly",
            "data": {
                "dates": [date_point.date() for date_point in dates],
                "pv": pv_series,
                "ac": ac_series,
                "ev": ev_series,
            },
        }

    def get_forecasts(
        self, project: Project, as_of_date: datetime, ev_method: str
    ) -> dict[str, Any]:
        """Calculate EVM forecasts for a project.

        Args:
            project: Project entity.
            as_of_date: Forecast baseline date.
            ev_method: EV calculation method (physical or milestone).

        Returns:
            Dictionary of forecast values.
        """
        tasks = self._get_tasks(project.id)
        milestones = self._get_milestones(project.id)
        expenses = self._get_expenses(project.id)
        rae_entries = self._get_rae_entries(project.id, as_of_date)

        bac = self._calculate_bac(tasks, project)
        pv = self._calculate_pv(tasks, as_of_date)
        ac = self._calculate_ac(expenses, as_of_date)

        rae_total, has_rae = self._calculate_total_rae(
            milestones, rae_entries, as_of_date
        )
        if not has_rae and bac is not None:
            rae_total = bac

        if ev_method == "milestone":
            ev = self._calculate_ev_milestone(bac, milestones, as_of_date)
        else:
            ev = self._calculate_ev_physical(bac, ac, rae_total)

        cpi = self._safe_divide(ev, ac)
        spi = self._safe_divide(ev, pv)

        eac_cpi = self._calculate_eac_cpi(bac, cpi)
        eac_cpi_spi = self._calculate_eac_cpi_spi(bac, ac, ev, cpi, spi)
        eac_plan = self._calculate_eac_plan(ac, pv, bac)

        return {
            "project_id": project.id,
            "as_of_date": as_of_date,
            "bac": bac,
            "ac": ac,
            "forecasts": {
                "cpi_method": {
                    "eac": eac_cpi,
                    "etc": self._safe_subtract(eac_cpi, ac),
                    "vac": self._safe_subtract(bac, eac_cpi),
                },
                "cpi_spi_method": {
                    "eac": eac_cpi_spi,
                    "etc": self._safe_subtract(eac_cpi_spi, ac),
                    "vac": self._safe_subtract(bac, eac_cpi_spi),
                },
                "plan_based": {
                    "eac": eac_plan,
                    "etc": self._safe_subtract(eac_plan, ac),
                    "vac": self._safe_subtract(bac, eac_plan),
                },
            },
        }

    def _get_tasks(self, project_id: Any) -> list[Task]:
        return self.db_session.query(Task).filter(Task.project_id == project_id).all()

    def _get_milestones(self, project_id: Any) -> list[Milestone]:
        return (
            self.db_session.query(Milestone)
            .filter(Milestone.project_id == project_id)
            .all()
        )

    def _get_expenses(self, project_id: Any) -> list[Expense]:
        return (
            self.db_session.query(Expense)
            .filter(Expense.project_id == project_id)
            .all()
        )

    def _get_rae_entries(
        self, project_id: Any, as_of_date: datetime
    ) -> list[MilestoneRAE]:
        return (
            self.db_session.query(MilestoneRAE)
            .join(Milestone, Milestone.id == MilestoneRAE.milestone_id)
            .filter(Milestone.project_id == project_id)
            .filter(MilestoneRAE.date <= as_of_date)
            .order_by(MilestoneRAE.milestone_id, MilestoneRAE.date.desc())
            .all()
        )

    def _calculate_bac(self, tasks: list[Task], project: Project) -> Decimal | None:
        total = Decimal("0")
        has_task_budget = False
        for task in tasks:
            if task.type == "summary":
                continue
            if task.planned_cost is None:
                continue
            total += self._to_decimal(task.planned_cost)
            has_task_budget = True

        if has_task_budget:
            return total

        if project.budget is None:
            return None
        return self._to_decimal(project.budget)

    def _calculate_pv(self, tasks: list[Task], as_of_date: datetime) -> Decimal:
        total = Decimal("0")
        for task in tasks:
            if task.type == "summary":
                continue
            if task.planned_cost is None:
                continue
            start = self._normalize_datetime(task.planned_start_date)
            finish = self._normalize_datetime(task.planned_finish_date)
            if start is None or finish is None:
                continue
            progress = self._calculate_linear_progress(start, finish, as_of_date)
            total += self._to_decimal(task.planned_cost) * progress
        return total

    def _calculate_ac(self, expenses: list[Expense], as_of_date: datetime) -> Decimal:
        total = Decimal("0")
        for expense in expenses:
            expense_date = self._normalize_datetime(expense.date)
            if expense_date and expense_date <= as_of_date:
                total += self._to_decimal(expense.amount)
        return total

    def _calculate_total_rae(
        self,
        milestones: list[Milestone],
        rae_entries: list[MilestoneRAE],
        as_of_date: datetime,
    ) -> tuple[Decimal | None, bool]:
        latest_by_milestone: dict[Any, MilestoneRAE] = {}
        for entry in rae_entries:
            if entry.date > as_of_date:
                continue
            if entry.milestone_id not in latest_by_milestone:
                latest_by_milestone[entry.milestone_id] = entry

        total = Decimal("0")
        has_rae = False

        for milestone in milestones:
            latest_entry: MilestoneRAE | None = latest_by_milestone.get(milestone.id)
            if latest_entry is not None:
                total += self._to_decimal(latest_entry.amount)
                has_rae = True
                continue
            if milestone.current_rae is not None:
                total += self._to_decimal(milestone.current_rae)
                has_rae = True

        return (total if has_rae else None), has_rae

    def _calculate_ev_physical(
        self, bac: Decimal | None, ac: Decimal | None, rae: Decimal | None
    ) -> Decimal | None:
        if bac is None:
            return None
        if ac is None:
            ac = Decimal("0")
        if rae is None:
            return None
        denominator = ac + rae
        if denominator <= 0:
            return Decimal("0")
        progress = ac / denominator
        return bac * progress

    def _calculate_ev_milestone(
        self,
        bac: Decimal | None,
        milestones: list[Milestone],
        as_of_date: datetime,
    ) -> Decimal | None:
        if bac is None:
            return None
        total_weight = Decimal("0")
        for milestone in milestones:
            if not milestone.is_achieved:
                continue
            achieved_date = self._normalize_datetime(milestone.achieved_date)
            if achieved_date and achieved_date > as_of_date:
                continue
            total_weight += self._to_decimal(milestone.budget_weight)
        return bac * total_weight

    def _calculate_eac_cpi(
        self, bac: Decimal | None, cpi: Decimal | None
    ) -> Decimal | None:
        if bac is None or cpi is None or cpi == 0:
            return None
        return bac / cpi

    def _calculate_eac_cpi_spi(
        self,
        bac: Decimal | None,
        ac: Decimal | None,
        ev: Decimal | None,
        cpi: Decimal | None,
        spi: Decimal | None,
    ) -> Decimal | None:
        if bac is None or ac is None or ev is None:
            return None
        if cpi is None or spi is None or cpi == 0 or spi == 0:
            return None
        remaining = bac - ev
        return ac + (remaining / (cpi * spi))

    def _calculate_eac_plan(
        self, ac: Decimal | None, pv: Decimal | None, bac: Decimal | None
    ) -> Decimal | None:
        if ac is None or pv is None or bac is None:
            return None
        remaining_pv = bac - pv
        return ac + remaining_pv

    def _build_month_end_dates(
        self, start_date: datetime, end_date: datetime
    ) -> list[datetime]:
        start = datetime(start_date.year, start_date.month, 1)
        end = datetime(end_date.year, end_date.month, 1)

        dates: list[datetime] = []
        current = start
        while current <= end:
            last_day = calendar.monthrange(current.year, current.month)[1]
            month_end = datetime(
                current.year,
                current.month,
                last_day,
                23,
                59,
                59,
                tzinfo=None,
            )
            if month_end >= start_date and month_end <= end_date:
                dates.append(month_end)
            current = self._next_month(current)

        return dates

    def _next_month(self, value: datetime) -> datetime:
        year = value.year + (value.month // 12)
        month = value.month % 12 + 1
        return datetime(year, month, 1)

    def _calculate_linear_progress(
        self, start: datetime, finish: datetime, as_of_date: datetime
    ) -> Decimal:
        if as_of_date <= start:
            return Decimal("0")
        if as_of_date >= finish:
            return Decimal("1")
        duration = (finish - start).total_seconds()
        if duration <= 0:
            return Decimal("1")
        progress = (as_of_date - start).total_seconds() / duration
        return Decimal(str(progress))

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _to_decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _safe_divide(
        self, numerator: Decimal | None, denominator: Decimal | None
    ) -> Decimal | None:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    def _safe_subtract(
        self, left: Decimal | None, right: Decimal | None
    ) -> Decimal | None:
        if left is None or right is None:
            return None
        return left - right

    def _to_period_series(self, values: list[Decimal]) -> list[Decimal]:
        period_values: list[Decimal] = []
        previous = Decimal("0")
        for value in values:
            period_values.append(value - previous)
            previous = value
        return period_values
