# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Excel-related commands for the interactive shell."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import click
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from poc_import.api.client import WfpApiClient, WfpApiError
from poc_import.cli_support import (
    console,
    log_duration,
    redact_secrets,
    set_correlation_id,
    setup_logging,
)
from poc_import.config import Config, load_env_file
from poc_import.models import (
    ExcelExpensesData,
    ExcelFileType,
    ExcelRAEData,
    ExpenseEntry,
)
from poc_import.parsers.excel import parse_expenses_excel, parse_rae_excel
from poc_import.shell_state import ShellState
from poc_import.validators import (
    ValidationReport,
    ValidationSeverity,
    validate_expense_rows,
    validate_rae_entries,
)


@click.group(
    help=(
        "Manipulating Excel files and imports.\n\n"
        "Commands:\n"
        "  load     Load an Excel file\n"
        "  list     List Excel entries (see help excel list)\n"
        "  show     Show Excel entries (see help excel show)\n"
        "  import   Import Excel entries"
    )
)
def excel() -> None:
    """Excel-related commands."""


def _require_loaded_excel(
    state: ShellState,
    expected_type: ExcelFileType,
) -> tuple[ExcelExpensesData | None, ExcelRAEData | None, ValidationReport | None]:
    if state.excel_type != expected_type:
        console.print(
            f"[red]Error:[/red] No {expected_type.value} Excel loaded. "
            "Use `excel load <file> --type` first."
        )
        sys.exit(1)
    return state.expenses_data, state.rae_data, state.excel_report


def _require_selected_project(state: ShellState) -> str:
    if not state.selected_project_id:
        console.print(
            "[red]Error:[/red] No project selected. "
            "Use `service select <project_id>` first."
        )
        sys.exit(1)
    return state.selected_project_id


def _format_amount(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}".replace(",", " ")


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else "-"


def _entry_has_errors(entry: ExpenseEntry, report: ValidationReport | None) -> bool:
    if report is None:
        return False
    entry_rows = set(entry.row_numbers)
    return any(
        issue.severity == ValidationSeverity.ERROR and issue.line in entry_rows
        for issue in report.checks
    )


def _print_validation_summary(report: ValidationReport) -> None:
    errors = report.summary.get("errors", 0)
    warnings = report.summary.get("warnings", 0)
    status = "✓ Passed" if errors == 0 else "✗ Failed"
    console.print(f"Validation: {status} ({errors} errors, {warnings} warnings)")
    if warnings:
        for issue in report.checks:
            if issue.severity == ValidationSeverity.WARNING:
                console.print(f"  [yellow]⚠[/yellow] {issue.message}")


def _get_xml_context(
    state: ShellState,
) -> tuple[set[str] | None, dict[str, date] | None]:
    if not state.data:
        return None, None
    task_names = {task.name for task in state.data.tasks if task.name}
    milestone_dates: dict[str, date] = {}
    for task in state.data.tasks:
        if not task.is_milestone or not task.name:
            continue
        planned_date = task.planned_finish_date or task.planned_start_date
        if planned_date:
            milestone_dates[task.name] = planned_date.date()
    return task_names, milestone_dates


def _extract_hours(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:[\.,]\d+)?)\s*h", value, flags=re.IGNORECASE)
    if not match:
        return None
    hours_text = match.group(1).replace(",", ".")
    try:
        return float(hours_text)
    except ValueError:
        return None


def _assign_milestone_by_date(
    expense_date: date | None,
    milestone_dates: dict[str, date] | None,
) -> tuple[str | None, date | None]:
    """Assign expense to milestone based on date range.

    Args:
        expense_date: Date of the expense.
        milestone_dates: Mapping of milestone name to planned date.

    Returns:
        Tuple of (milestone_name, milestone_date) if assigned, else (None, None).
    """
    if not expense_date or not milestone_dates:
        return None, None

    sorted_milestones = sorted(milestone_dates.items(), key=lambda x: x[1])
    for milestone_name, milestone_date in sorted_milestones:
        if expense_date <= milestone_date:
            return milestone_name, milestone_date

    if sorted_milestones:
        return sorted_milestones[-1]
    return None, None


@click.command("load")
@click.argument("excel_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--type",
    "excel_type",
    type=click.Choice(["expenses", "rae"], case_sensitive=False),
    required=True,
    help="Excel file type",
)
@click.pass_obj
def excel_load(state: ShellState, excel_file: Path, excel_type: str) -> None:
    """Load Excel file into memory and validate immediately."""
    setup_logging(verbose=False)
    start_time = time.monotonic()
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    if excel_type.lower() == ExcelFileType.EXPENSES.value:
        try:
            expenses_data = parse_expenses_excel(excel_file)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)

        report = validate_expense_rows(expenses_data.rows)
        state.excel_path = excel_file
        state.excel_type = ExcelFileType.EXPENSES
        state.expenses_data = expenses_data
        state.rae_data = None
        state.excel_report = report

        console.print(f"[green]✓[/green] Excel loaded: {excel_file.name}\n")
        console.print("Type: Expenses")
        console.print(f'Sheet: "{expenses_data.sheet_name}"\n')
        console.print("Data Summary:")
        console.print(f"  - Total Rows: {expenses_data.total_rows}")
        if expenses_data.period_start and expenses_data.period_end:
            console.print(
                "  - Period: "
                f"{expenses_data.period_start.strftime('%Y-%m')} to "
                f"{expenses_data.period_end.strftime('%Y-%m')}"
            )
        console.print(
            f"  - Total Amount: {_format_amount(expenses_data.total_amount)} EUR"
        )
        console.print(
            "  - Unique References: "
            f"{expenses_data.unique_references} ({expenses_data.grouped_count} grouped)"
        )
        console.print(
            f"  - Missing References: {expenses_data.missing_references} rows"
        )
        console.print("\nBreakdown by Type:")
        console.print(
            f"  - Achats (Purchases): {expenses_data.purchase_rows} rows, "
            f"{_format_amount(expenses_data.purchase_amount)} EUR"
        )
        console.print(
            f"  - Pointages (Time tracking): {expenses_data.time_rows} rows, "
            f"{_format_amount(expenses_data.time_amount)} EUR"
        )
        console.print("")
        _print_validation_summary(report)
        console.print(
            "\nUse 'excel list expenses' to view entries or "
            "'excel import expenses' to import."
        )

        if report.has_errors():
            sys.exit(2)

    else:
        try:
            data = parse_rae_excel(excel_file)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error:[/red] {exc}")
            sys.exit(1)

        task_names, milestone_dates = _get_xml_context(state)
        milestone_names = set(milestone_dates.keys()) if milestone_dates else None
        report = validate_rae_entries(
            data.entries,
            milestone_names=milestone_names,
            task_names=task_names,
            milestone_dates=milestone_dates,
        )

        state.excel_path = excel_file
        state.excel_type = ExcelFileType.RAE
        state.rae_data = data
        state.expenses_data = None
        state.excel_report = report

        console.print(f"[green]✓[/green] Excel loaded: {excel_file.name}\n")
        console.print("Type: RAE (Reste À Engager)")
        console.print(f'Sheet: "{data.sheet_name}"\n')
        console.print("Data Summary:")
        console.print(f"  - Total Rows: {data.total_rows}")
        console.print(f"  - Milestones: {data.milestone_count}")
        console.print(
            f"  - Total Remaining Budget: {_format_amount(data.total_remaining)} EUR"
        )
        if data.forecast_period:
            console.print(f"  - Forecast Period: {data.forecast_period}")
        console.print("")
        _print_validation_summary(report)
        console.print(
            "\nUse 'excel list rae' to view entries or 'excel import rae' to import."
        )

        if report.has_errors():
            sys.exit(2)

    log_duration(start_time, "excel load", logging.getLogger(__name__))


@click.group("list", help="List Excel entries")
def excel_list() -> None:
    """List Excel entries."""


@excel_list.command("expenses")
@click.option("--year", type=int, help="Filter by fiscal year")
@click.option("--month", type=int, help="Filter by period (1-12)")
@click.option(
    "--sort-by",
    type=click.Choice(["date", "amount", "reference"], case_sensitive=False),
    default="date",
    show_default=True,
    help="Sort column",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def excel_list_expenses(
    state: ShellState,
    year: int | None,
    month: int | None,
    sort_by: str,
    output: str,
) -> None:
    """List loaded expenses entries."""
    expenses_data, _rae_data, _report = _require_loaded_excel(
        state, ExcelFileType.EXPENSES
    )
    data = expenses_data
    if data is None:
        console.print("[red]Error:[/red] Expenses data not available.")
        sys.exit(1)

    entries = data.entries
    if year is not None:
        entries = [entry for entry in entries if entry.fiscal_year == year]
    if month is not None:
        entries = [entry for entry in entries if entry.period == month]

    if sort_by.lower() == "amount":
        entries = sorted(entries, key=lambda entry: entry.amount)
    elif sort_by.lower() == "reference":
        entries = sorted(entries, key=lambda entry: entry.reference_number or "")
    else:
        entries = sorted(entries, key=lambda entry: entry.expense_date or date.min)

    if output.lower() == "json":
        payload = {
            "data": [_expense_entry_to_json(entry) for entry in entries],
            "total": data.total_rows,
            "total_amount": round(data.total_amount, 2),
            "currency": "EUR",
            "unique_references": data.unique_references,
            "grouped_count": data.grouped_count,
        }
        console.print(json.dumps(payload, indent=2, default=str))
        return

    console.print(f"Expenses ({data.total_rows} total, showing grouped entries):\n")
    table = Table(show_lines=False)
    table.add_column("ID", justify="right")
    table.add_column("Reference")
    table.add_column("Date")
    table.add_column("Amount", justify="right")
    table.add_column("Type")
    table.add_column("Description/Resource")

    for entry in entries:
        entry_type = "Achat" if entry.purchase_document else "Pointage"
        description = entry.description or entry.resource_name or "-"
        table.add_row(
            str(entry.entry_id),
            entry.reference_number or "-",
            _format_date(entry.expense_date),
            _format_amount(entry.amount),
            entry_type,
            description,
        )

    console.print(table)
    console.print("")
    console.print(f"Total: {_format_amount(data.total_amount)} EUR")
    console.print("\nUse 'excel show expense <id>' for full details.")


@excel_list.command("rae")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def excel_list_rae(state: ShellState, output: str) -> None:
    """List loaded RAE entries."""
    _expenses_data, rae_data, _report = _require_loaded_excel(state, ExcelFileType.RAE)
    data = rae_data
    if data is None:
        console.print("[red]Error:[/red] RAE data not available.")
        sys.exit(1)

    if output.lower() == "json":
        payload = {
            "data": [_rae_entry_to_json(entry) for entry in data.entries],
            "total": data.milestone_count,
            "total_rae": round(data.total_remaining, 2),
            "currency": "EUR",
        }
        console.print(json.dumps(payload, indent=2, default=str))
        return

    console.print(f"RAE - Reste À Engager ({len(data.entries)} entries):\n")
    table = Table(show_lines=False)
    table.add_column("ID", justify="right")
    table.add_column("Milestone")
    table.add_column("Remaining Budget", justify="right")
    table.add_column("Forecast Date")
    table.add_column("Task Breakdown")

    for entry in data.entries:
        breakdown = (
            f"{len(entry.task_breakdown)} tasks" if entry.task_breakdown else "-"
        )
        table.add_row(
            str(entry.entry_id),
            entry.milestone_name,
            _format_amount(entry.remaining_amount),
            _format_date(entry.forecast_date),
            breakdown,
        )
    console.print(table)
    console.print("")
    console.print(f"Total RAE: {_format_amount(data.total_remaining)} EUR")
    console.print("\nUse 'excel show rae <id>' for details.")


@click.group("show", help="Show Excel entries")
def excel_show() -> None:
    """Show Excel entry details."""


@excel_show.command("expense")
@click.argument("expense_id", type=int)
@click.pass_obj
def excel_show_expense(state: ShellState, expense_id: int) -> None:
    """Show details for a single expense entry."""
    expenses_data, _rae_data, report = _require_loaded_excel(
        state, ExcelFileType.EXPENSES
    )
    data = expenses_data
    if data is None:
        console.print("[red]Error:[/red] Expenses data not available.")
        sys.exit(1)

    entry = next((item for item in data.entries if item.entry_id == expense_id), None)
    if entry is None:
        console.print(f"[red]Error:[/red] Expense ID {expense_id} not found.")
        sys.exit(1)

    entry_type = (
        "Achat (Purchase)" if entry.purchase_document else "Pointage (Time Tracking)"
    )
    console.print(f"Expense #{entry.entry_id}\n")
    console.print(f"[Type] {entry_type}\n")

    console.print("[Reference]")
    if entry.purchase_document:
        console.print(f"  Document d'achat: {entry.purchase_document}")
    console.print(f"  Nº pièce référence: {entry.reference_number or '-'}")
    if entry.purchase_reference:
        console.print(f"  Référence: {entry.purchase_reference}")
    console.print("")

    console.print("[Financial]")
    console.print(f"  Amount: {_format_amount(entry.amount)} EUR")
    if entry.fiscal_year is not None:
        console.print(f"  Exercice comptable: {entry.fiscal_year}")
    if entry.period is not None:
        console.print(f"  Période: {entry.period}")
    console.print(f"  Date: {_format_date(entry.expense_date)}\n")

    console.print("[Classification]")
    if entry.accounting_nature_label:
        console.print(f"  Désign.nat.comptable: {entry.accounting_nature_label}")
    if entry.otp_element:
        console.print(f"  Elément d'OTP: {entry.otp_element}")
    console.print("")

    if entry.purchase_document:
        console.print("[Supplier]")
        if entry.vendor_name:
            console.print(f"  Nom 1: {entry.vendor_name}")
        console.print("")
        if entry.description:
            console.print("[Description]")
            console.print(f"  Texte: {entry.description}")
            console.print("")
    else:
        console.print("[Resource]")
        if entry.resource_name:
            console.print(f"  Nom Matricule: {entry.resource_name}")
        hours = _extract_hours(entry.description) or _extract_hours(entry.resource_name)
        if hours and hours > 0:
            rate = entry.amount / hours
            console.print(f"  Hours: {hours:g}h")
            console.print(f"  Rate: {_format_amount(rate)} EUR/h")
        console.print("")

    ready = "Yes" if not _entry_has_errors(entry, report) else "No"
    console.print("[Status]")
    console.print(f"  Ready to import: {ready}")
    _task_names, milestone_dates = _get_xml_context(state)
    if milestone_dates:
        milestone_name, milestone_date = _assign_milestone_by_date(
            entry.expense_date, milestone_dates
        )
        if milestone_name and milestone_date:
            console.print(
                f"  Target Milestone: {milestone_name} "
                f"(assigned by date: {milestone_date.isoformat()})"
            )


@excel_show.command("rae")
@click.argument("rae_id", type=int)
@click.pass_obj
def excel_show_rae(state: ShellState, rae_id: int) -> None:
    """Show details for a single RAE entry."""
    _expenses_data, rae_data, report = _require_loaded_excel(state, ExcelFileType.RAE)
    data = rae_data
    if data is None:
        console.print("[red]Error:[/red] RAE data not available.")
        sys.exit(1)

    entry = next((item for item in data.entries if item.entry_id == rae_id), None)
    if entry is None:
        console.print(f"[red]Error:[/red] RAE ID {rae_id} not found.")
        sys.exit(1)

    console.print(f"RAE Entry #{entry.entry_id}\n")
    console.print("[Milestone]")
    console.print(f"  Name: {entry.milestone_name}")
    console.print(f"  Forecast Date: {_format_date(entry.forecast_date)}\n")

    console.print("[Budget]")
    console.print(f"  Remaining Amount: {_format_amount(entry.remaining_amount)} EUR")
    if entry.task_breakdown:
        console.print(
            f"  Allocated to Tasks: {_format_amount(entry.breakdown_sum)} EUR"
        )
        if entry.remaining_amount is not None:
            unallocated = entry.remaining_amount - entry.breakdown_sum
            console.print(f"  Unallocated: {_format_amount(unallocated)} EUR")
    console.print("")

    if entry.task_breakdown:
        console.print(f"[Task Breakdown] ({len(entry.task_breakdown)} tasks)")
        for item in entry.task_breakdown:
            console.print(f"  - {item.task_name}: {_format_amount(item.amount)} EUR")
        console.print("")

    task_names, milestone_dates = _get_xml_context(state)
    milestone_names = set(milestone_dates.keys()) if milestone_dates else None
    entry_report = validate_rae_entries(
        [entry],
        milestone_names=milestone_names,
        task_names=task_names,
        milestone_dates=milestone_dates,
    )
    issues = entry_report.checks

    console.print("[Validation]")

    if entry.task_breakdown and entry.breakdown_sum == entry.remaining_amount:
        console.print("  [green]✓[/green] Sum of task breakdown equals milestone RAE")
    elif entry.task_breakdown:
        console.print(
            "  [red]✗[/red] Sum of task breakdown does not match milestone RAE"
        )

    if task_names and entry.task_breakdown:
        missing_tasks = [
            item.task_name
            for item in entry.task_breakdown
            if item.task_name not in task_names
        ]
        if not missing_tasks:
            console.print("  [green]✓[/green] All tasks exist in loaded XML")
        else:
            console.print(
                f"  [red]✗[/red] Tasks not found in XML: {', '.join(missing_tasks)}"
            )

    if milestone_dates and entry.milestone_name and entry.forecast_date:
        expected_date = milestone_dates.get(entry.milestone_name)
        if expected_date and entry.forecast_date == expected_date:
            console.print("  [green]✓[/green] Milestone date matches XML")
        elif expected_date:
            console.print(
                f"  [yellow]⚠[/yellow] Milestone date mismatch: "
                f"forecast={entry.forecast_date.isoformat()}, "
                f"XML={expected_date.isoformat()}"
            )

    for issue in issues:
        if issue.id not in ["VAL-RAE-004", "VAL-RAE-005", "VAL-RAE-006"]:
            marker = "✓" if issue.severity == ValidationSeverity.WARNING else "✗"
            color = "yellow" if issue.severity == ValidationSeverity.WARNING else "red"
            console.print(f"  [{color}]{marker}[/{color}] {issue.message}")


@click.group("import", help="Import Excel entries")
def excel_import() -> None:
    """Import Excel entries into the API."""


@excel_import.command("expenses")
@click.option("--dry-run", is_flag=True, help="Validate without executing")
@click.option(
    "--skip-existing/--no-skip-existing",
    default=True,
    show_default=True,
    help="Skip expenses with existing reference numbers",
)
@click.option(
    "--env",
    "env_name",
    type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
    help="Environment to load (.env.dev/.env.staging/.env.prod)",
)
@click.option(
    "--token",
    type=str,
    envvar="WFP_JWT_TOKEN",
    help="JWT authentication token",
)
@click.option(
    "--api-url",
    type=str,
    envvar="WFP_API_URL",
    default="http://localhost:5000",
    help="wfp-poc API base URL",
)
@click.option(
    "--company-id",
    type=str,
    help="Company UUID for multi-tenant isolation (optional)",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["debug", "info", "warning", "error", "critical"], case_sensitive=False
    ),
    help="Logging level",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_obj
def excel_import_expenses(
    state: ShellState,
    dry_run: bool,
    skip_existing: bool,
    env_name: str | None,
    token: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Import expenses to the API."""
    expenses_data, _rae_data, report = _require_loaded_excel(
        state, ExcelFileType.EXPENSES
    )
    data = expenses_data
    if data is None:
        console.print("[red]Error:[/red] Expenses data not available.")
        sys.exit(1)

    project_id = _require_selected_project(state)
    setup_logging(verbose, log_level)
    load_env_file(env_name)
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    config = Config()
    start_time = time.monotonic()

    report = report or validate_expense_rows(data.rows)
    if report.has_errors():
        console.print("[red]✗ Validation failed. Fix errors before import.[/red]")
        _print_validation_summary(report)
        sys.exit(2)

    console.print("Starting expense import...\n")
    console.print(
        f"Target Project: {state.selected_project_name or project_id} "
        f"(id: {project_id})\n"
    )
    console.print("Pre-import validation: ✓ Passed\n")

    if dry_run:
        console.print("[yellow]Dry run:[/yellow] Skipping API calls")
        sys.exit(0)

    api_url = api_url or config.api_url
    token = token or config.jwt_token or config.build_jwt_token()
    if not token:
        console.print(
            "[red]Error:[/red] --token is required (or set WFP_JWT_TOKEN env var)"
        )
        sys.exit(1)

    client = WfpApiClient(
        api_url,
        token,
        correlation_id=correlation_id,
        company_id=company_id,
    )

    entries = data.entries
    skipped = 0
    if skip_existing:
        existing_refs = _fetch_existing_expense_refs(client, project_id)
        filtered = []
        for entry in entries:
            if entry.reference_number and entry.reference_number in existing_refs:
                skipped += 1
                continue
            filtered.append(entry)
        entries = filtered

    if not entries:
        console.print("[yellow]No expenses to import after filtering.[/yellow]")
        sys.exit(0)

    total_amount = sum(entry.amount for entry in entries)
    created_total = 0

    console.print("Importing expenses...")
    with Progress(
        TextColumn(
            "Importing expenses: {task.completed}/{task.total} "
            "({task.percentage:>3.0f}%)"
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Expenses", total=len(entries))
        batch_size = config.batch_size_expenses
        for batch in _chunk_entries(entries, batch_size):
            payload = [_expense_entry_to_payload(entry) for entry in batch]
            try:
                response = client.bulk_create_expenses(project_id, payload)
            except WfpApiError as exc:
                console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
                sys.exit(1)

            data_response = response.get("data", {})
            created = int(data_response.get("created_count", 0))
            failed = int(data_response.get("failed_count", 0))
            created_total += created
            if failed:
                console.print("[red]✗ Import failed due to validation errors.[/red]")
                for error in data_response.get("errors", []):
                    console.print(
                        f"  [red]Error:[/red] index {error.get('index')}: "
                        f"{error.get('error')}"
                    )
                sys.exit(1)

            progress.update(task_id, advance=len(batch))

    console.print("\n[green]✓ Import completed successfully[/green]\n")
    console.print("Summary:")
    console.print(f"  - Expenses created: {created_total}")
    if skipped:
        console.print(f"  - Skipped (duplicates): {skipped}")
    console.print(f"  - Total amount imported: {_format_amount(total_amount)} EUR")
    log_duration(start_time, "excel import expenses", logging.getLogger(__name__))


@excel_import.command("rae")
@click.option("--dry-run", is_flag=True, help="Validate without executing")
@click.option(
    "--env",
    "env_name",
    type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
    help="Environment to load (.env.dev/.env.staging/.env.prod)",
)
@click.option(
    "--token",
    type=str,
    envvar="WFP_JWT_TOKEN",
    help="JWT authentication token",
)
@click.option(
    "--api-url",
    type=str,
    envvar="WFP_API_URL",
    default="http://localhost:5000",
    help="wfp-poc API base URL",
)
@click.option(
    "--company-id",
    type=str,
    help="Company UUID for multi-tenant isolation (optional)",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["debug", "info", "warning", "error", "critical"], case_sensitive=False
    ),
    help="Logging level",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_obj
def excel_import_rae(
    state: ShellState,
    dry_run: bool,
    env_name: str | None,
    token: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Import RAE entries to the API."""
    _expenses_data, rae_data, report = _require_loaded_excel(state, ExcelFileType.RAE)
    data = rae_data
    if data is None:
        console.print("[red]Error:[/red] RAE data not available.")
        sys.exit(1)

    project_id = _require_selected_project(state)
    setup_logging(verbose, log_level)
    load_env_file(env_name)
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    config = Config()
    start_time = time.monotonic()

    api_url = api_url or config.api_url
    token = token or config.jwt_token or config.build_jwt_token()
    if not token:
        console.print(
            "[red]Error:[/red] --token is required (or set WFP_JWT_TOKEN env var)"
        )
        sys.exit(1)

    client = WfpApiClient(
        api_url,
        token,
        correlation_id=correlation_id,
        company_id=company_id,
    )
    milestones = client.get_project_milestones(project_id)
    milestone_map = {
        milestone.get("name"): milestone.get("id") for milestone in milestones
    }
    task_names, milestone_dates = _get_xml_context(state)
    report = validate_rae_entries(
        data.entries,
        milestone_names={str(k) for k in milestone_map.keys() if k is not None},
        task_names=task_names,
        milestone_dates=milestone_dates,
    )
    if report.has_errors():
        console.print("[red]✗ Validation failed. Fix errors before import.[/red]")
        _print_validation_summary(report)
        sys.exit(2)

    console.print("Starting RAE import...\n")
    console.print(
        f"Target Project: {state.selected_project_name or project_id} "
        f"(id: {project_id})\n"
    )
    console.print("Pre-import validation: ✓ Passed\n")

    if dry_run:
        console.print("[yellow]Dry run:[/yellow] Skipping API calls")
        sys.exit(0)

    task_map = _fetch_task_name_map(client, project_id)
    updated_count = 0
    breakdown_count = 0
    total_amount = sum(entry.remaining_amount or 0.0 for entry in data.entries)

    console.print("Importing RAE entries...")
    with Progress(
        TextColumn(
            "Importing RAE: {task.completed}/{task.total} ({task.percentage:>3.0f}%)"
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("RAE", total=len(data.entries))
        for entry in data.entries:
            milestone_id = milestone_map.get(entry.milestone_name)
            if not milestone_id:
                console.print(
                    f"[red]Error:[/red] Milestone not found: {entry.milestone_name}"
                )
                sys.exit(2)

            if entry.remaining_amount is None:
                console.print(
                    "[red]Error:[/red] Missing remaining_amount for RAE entry "
                    f"{entry.entry_id}"
                )
                sys.exit(2)

            payload = {
                "date": _format_api_date(entry.forecast_date),
                "amount": entry.remaining_amount,
            }
            details = _build_rae_details(entry, task_map)
            if details:
                payload["details"] = details
                breakdown_count += len(details.get("task_estimates", []))

            try:
                client.create_milestone_rae(milestone_id, payload)
            except WfpApiError as exc:
                console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
                sys.exit(1)

            updated_count += 1
            progress.update(task_id, advance=1)

    console.print("\n[green]✓ Import completed successfully[/green]\n")
    console.print("Summary:")
    console.print(f"  - Milestones updated: {updated_count}")
    console.print(f"  - Total RAE amount: {_format_amount(total_amount)} EUR")
    if breakdown_count:
        console.print(f"  - Task breakdowns: {breakdown_count} entries")
    log_duration(start_time, "excel import rae", logging.getLogger(__name__))


def _chunk_entries(entries: list[ExpenseEntry], size: int) -> list[list[ExpenseEntry]]:
    return [entries[i : i + size] for i in range(0, len(entries), size)]


def _fetch_existing_expense_refs(client: WfpApiClient, project_id: str) -> set[str]:
    refs: set[str] = set()
    page = 1
    per_page = 100
    while True:
        response = client.list_project_expenses(
            project_id, page=page, per_page=per_page
        )
        data = response.get("data", [])
        for expense in data:
            ref = expense.get("reference_number")
            if ref:
                refs.add(ref)
        total_pages = int(response.get("total_pages", page))
        if page >= total_pages:
            break
        page += 1
    return refs


def _expense_entry_to_payload(entry: ExpenseEntry) -> dict[str, Any]:
    return {
        "date": _format_api_date(entry.expense_date),
        "amount": entry.amount,
        "category": entry.category,
        "description": entry.description,
        "reference_number": entry.reference_number,
        "purchase_document": entry.purchase_document,
        "fiscal_year": entry.fiscal_year,
        "period": entry.period,
        "otp_element": entry.otp_element,
        "accounting_nature": entry.accounting_nature,
        "vendor_name": entry.vendor_name or entry.resource_name,
        "origin_group": entry.origin_group,
    }


def _format_api_date(value: date | None) -> str:
    if value is None:
        return ""
    return f"{value.isoformat()}T00:00:00Z"


def _expense_entry_to_json(entry: ExpenseEntry) -> dict[str, Any]:
    resource_name, resource_id = _split_resource_name(entry.resource_name)
    payload: dict[str, Any] = {
        "id": entry.entry_id,
        "reference_number": entry.reference_number,
        "date": entry.expense_date.isoformat() if entry.expense_date else None,
        "amount": round(entry.amount, 2),
        "category": entry.category,
        "description": entry.description,
        "vendor_name": entry.vendor_name,
        "otp_element": entry.otp_element,
        "fiscal_year": entry.fiscal_year,
        "period": entry.period,
    }
    if resource_name:
        payload["resource_name"] = resource_name
    if resource_id:
        payload["resource_matricule"] = resource_id
    return payload


def _rae_entry_to_json(entry: Any) -> dict[str, Any]:
    remaining = (
        round(entry.remaining_amount, 2) if entry.remaining_amount is not None else None
    )
    return {
        "id": entry.entry_id,
        "milestone_name": entry.milestone_name,
        "remaining_amount": remaining,
        "forecast_date": (
            entry.forecast_date.isoformat() if entry.forecast_date else None
        ),
        "task_breakdown": [
            {"task_name": item.task_name, "amount": item.amount}
            for item in entry.task_breakdown
        ],
        "task_count": len(entry.task_breakdown),
        "breakdown_sum": round(entry.breakdown_sum, 2),
    }


def _split_resource_name(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = re.match(r"^(.*?)\s*\(ID:\s*([^\)]+)\)", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return value, None


def _fetch_task_name_map(client: WfpApiClient, project_id: str) -> dict[str, str]:
    task_map: dict[str, str] = {}
    page = 1
    per_page = 200
    while True:
        response = client.list_project_tasks(project_id, page=page, per_page=per_page)
        tasks = response.get("data", [])
        for task in tasks:
            name = task.get("name")
            task_id = task.get("id")
            if name and task_id and name not in task_map:
                task_map[name] = task_id
        total_pages = int(response.get("total_pages", page))
        if page >= total_pages:
            break
        page += 1
    return task_map


def _build_rae_details(entry: Any, task_map: dict[str, str]) -> dict[str, Any] | None:
    if not entry.task_breakdown:
        return None
    task_estimates = []
    for item in entry.task_breakdown:
        task_id = task_map.get(item.task_name)
        if not task_id:
            console.print(
                "[yellow]Warning:[/yellow] Task not found for breakdown: "
                f"{item.task_name}"
            )
            continue
        task_estimates.append(
            {
                "task_id": task_id,
                "task_name": item.task_name,
                "remaining_cost": item.amount,
                "comment": item.comment,
            }
        )
    if not task_estimates:
        return None
    return {"task_estimates": task_estimates}


excel.add_command(excel_load)
excel.add_command(excel_list)
excel.add_command(excel_show)
excel.add_command(excel_import)
