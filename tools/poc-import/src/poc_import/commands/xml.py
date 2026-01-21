# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""XML inspection and import commands for the interactive shell."""

import csv
import html
import json
import sys
import time
import uuid
from datetime import datetime
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
    redact_secrets,
    set_correlation_id,
    setup_logging,
)
from poc_import.config import Config, load_env_file
from poc_import.models import MSProjectData
from poc_import.parsers.msproject import MSProjectParser
from poc_import.shell_state import ShellState
from poc_import.validators import ValidationReport, validate_msproject_rules


@click.group(
    help=(
        "Manipulating XML files and objects.\n\n"
        "Commands:\n"
        "  load  Load an XML file\n"
        "  list  List XML entities (see help xml list)\n"
        "  show  Show XML entities (see help xml show)\n"
        "  validate  Validate XML entities\n"
        "  import  Import XML entities"
    )
)
def xml() -> None:
    """XML-related commands."""


def _require_loaded_xml(state: ShellState) -> MSProjectData:
    """Ensure XML is loaded in the shell state.

    Args:
        state: Shell state containing parsed XML data.
    """
    if not state.data:
        console.print("[red]Error:[/red] No XML loaded. Use `xml load <file>`.")
        sys.exit(1)
    return state.data


def _require_selected_project(state: ShellState) -> str:
    """Return selected project ID or exit with a helpful error.

    Args:
        state: Shell state containing selected project.

    Returns:
        Selected project ID.
    """
    if not state.selected_project_id:
        console.print(
            "[red]Error:[/red] No project selected. "
            "Use `service select <project_id>` first."
        )
        sys.exit(1)
    return state.selected_project_id


def _render_validation_html(report: ValidationReport) -> str:
    """Render validation report as HTML.

    Args:
        report: Validation report to render.

    Returns:
        HTML string.
    """
    rows = []
    for issue in report.checks:
        rows.append(
            "<tr>"
            f"<td>{html.escape(issue.severity.value)}</td>"
            f"<td>{html.escape(issue.id)}</td>"
            f"<td>{html.escape(issue.message)}</td>"
            f"<td>{html.escape(str(issue.line)) if issue.line else ''}</td>"
            "</tr>"
        )
    summary = report.summary
    return (
        "<html><body>"
        "<h1>Validation Report</h1>"
        "<table border='1'>"
        "<tr><th>Severity</th><th>Rule</th><th>Message</th><th>Line</th></tr>"
        + "".join(rows)
        + "</table>"
        "<p>Summary: "
        f"{summary.get('errors', 0)} errors, "
        f"{summary.get('warnings', 0)} warnings</p>"
        "</body></html>"
    )


def _build_client(
    api_url: str,
    token: str | None,
    company_id: str | None,
    env_name: str | None,
) -> WfpApiClient:
    """Build API client with configuration and token handling.

    Args:
        api_url: Base API URL.
        token: JWT token or None to load from env.
        company_id: Optional company UUID.
        env_name: Environment name to load.

    Returns:
        Configured API client.
    """
    load_env_file(env_name)
    config = Config()

    api_url = api_url or config.api_url
    company_id = company_id or config.company_id
    if not token:
        token = config.jwt_token
    if not token:
        token = config.build_jwt_token()
    if not token:
        console.print(
            "[red]Error:[/red] --token is required (or set WFP_JWT_TOKEN env var)"
        )
        console.print(
            "[yellow]Tip:[/yellow] Set JWT_SECRET_KEY + WFP_USER_ID/WFP_COMPANY_ID "
            "in tools/poc-import/.env to auto-generate a token."
        )
        sys.exit(1)

    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    return WfpApiClient(
        base_url=api_url,
        token=token,
        correlation_id=correlation_id,
        company_id=company_id,
    )


def _print_json(data: dict[str, Any]) -> None:
    """Print JSON output using the rich console.

    Args:
        data: Data payload to print as JSON.
    """
    console.print_json(json.dumps(data))


def _print_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Print CSV output to stdout.

    Args:
        rows: Rows of data to print.
        fieldnames: CSV column order.
    """
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def _extract_dependency_ids(result: dict[str, Any]) -> set[str]:
    """Extract dependency IDs from API response.

    Args:
        result: API response containing dependency data.

    Returns:
        Set of dependency UUIDs.
    """
    items = result.get("data", [])
    if not isinstance(items, list):
        return set()
    ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            dep_id = item.get("id")
            if isinstance(dep_id, str):
                ids.add(dep_id)
    return ids


def _extract_project_id(response: dict[str, Any]) -> str:
    """Extract project ID from API response.

    Args:
        response: API response payload.

    Returns:
        Project UUID string.

    Raises:
        ValueError: If project ID cannot be found.
    """
    project_id = response.get("data", {}).get("id") or response.get("id")
    if not project_id:
        raise ValueError("Project ID not found in response")
    return str(project_id)


def _import_project_entities(
    client: WfpApiClient,
    project_id: str,
    data: MSProjectData,
    continue_on_error: bool,
) -> dict[str, list[str]]:
    """Import tasks, resources, assignments, and dependencies.

    Args:
        client: API client.
        project_id: Project UUID.
        data: Parsed MS Project data.
        continue_on_error: Continue on error flag.

    Returns:
        Dict with created entity IDs.
    """
    created_task_ids: list[str] = []
    created_resource_ids: list[str] = []
    created_assignment_ids: list[str] = []
    created_dependency_ids: list[str] = []

    task_map: dict[int, str] = {}
    resource_map: dict[int, str] = {}

    def _handle_import_error(
        exc: WfpApiError,
        created_tasks: list[str],
        created_resources: list[str],
        created_assignments: list[str],
        created_deps: list[str] | None = None,
    ) -> None:
        """Handle import error with rollback.

        Args:
            exc: The API error that occurred.
            created_tasks: List of created task IDs.
            created_resources: List of created resource IDs.
            created_assignments: List of created assignment IDs.
            created_deps: Optional list of created dependency IDs.
        """
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        if not continue_on_error:
            console.print("\n[red]✗ Import failed. Rolling back...[/red]")
            rollback = client.rollback_import(
                project_id,
                task_ids=created_tasks,
                assignment_ids=created_assignments,
                resource_ids=created_resources,
                dependency_ids=created_deps or [],
            )
            _print_rollback_failures(rollback.get("failed", []))
            sys.exit(1)

    console.print("\n[bold]Importing tasks...[/bold]")
    with Progress(
        TextColumn(
            "Importing tasks: {task.completed}/{task.total} ({task.percentage:>3.0f}%)"
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_progress = progress.add_task("Tasks", total=len(data.tasks))
        for task in data.tasks:
            try:
                result = client.create_task(project_id, task)
                task_id = result.get("task_id")
                task_map.update(result.get("task_map", {}))
                if task_id:
                    created_task_ids.append(task_id)
            except WfpApiError as exc:
                _handle_import_error(
                    exc,
                    created_task_ids,
                    created_resource_ids,
                    created_assignment_ids,
                )
            finally:
                progress.update(task_progress, advance=1)

    console.print("\n[bold]Importing resources...[/bold]")
    with Progress(
        TextColumn(
            "Importing resources: {task.completed}/{task.total} "
            "({task.percentage:>3.0f}%)"
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        res_progress = progress.add_task("Resources", total=len(data.resources))
        for resource in data.resources:
            try:
                result = client.create_resource(resource)
                resource_id = result.get("resource_id")
                resource_map.update(result.get("resource_map", {}))
                if resource_id:
                    created_resource_ids.append(resource_id)
            except WfpApiError as exc:
                _handle_import_error(
                    exc,
                    created_task_ids,
                    created_resource_ids,
                    created_assignment_ids,
                )
            finally:
                progress.update(res_progress, advance=1)

    console.print("\n[bold]Importing assignments...[/bold]")
    with Progress(
        TextColumn(
            "Importing assignments: {task.completed}/{task.total} "
            "({task.percentage:>3.0f}%)"
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        assign_progress = progress.add_task(
            "Assignments",
            total=len(data.assignments),
        )
        for assignment in data.assignments:
            try:
                result = client.create_assignment(
                    project_id,
                    assignment,
                    task_map,
                    resource_map,
                )
                assignment_id = result.get("assignment_id")
                if assignment_id:
                    created_assignment_ids.append(assignment_id)
            except WfpApiError as exc:
                _handle_import_error(
                    exc,
                    created_task_ids,
                    created_resource_ids,
                    created_assignment_ids,
                )
            finally:
                progress.update(assign_progress, advance=1)

    console.print("\n[bold]Importing dependencies...[/bold]")
    if data.dependencies:
        with Progress(
            TextColumn(
                "Importing dependencies: {task.completed}/{task.total} "
                "({task.percentage:>3.0f}%)"
            ),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            dep_progress = progress.add_task(
                "Dependencies",
                total=len(data.dependencies),
            )
            try:
                client.sync_tasks(project_id, data.tasks)
                progress.update(
                    dep_progress,
                    completed=len(data.dependencies),
                )
                console.print("[green]✓[/green] Dependencies applied")
            except WfpApiError as exc:
                console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
                if not continue_on_error:
                    console.print("\n[red]✗ Import failed. Rolling back...[/red]")
                    rollback = client.rollback_import(
                        project_id,
                        task_ids=created_task_ids,
                        assignment_ids=created_assignment_ids,
                        resource_ids=created_resource_ids,
                        dependency_ids=created_dependency_ids,
                    )
                    _print_rollback_failures(rollback.get("failed", []))
                    sys.exit(1)

    return {
        "tasks": created_task_ids,
        "resources": created_resource_ids,
        "assignments": created_assignment_ids,
        "dependencies": created_dependency_ids,
    }


def _print_field(name: str, value: Any, imported: bool) -> None:
    """Print a field with imported/display-only styling.

    Args:
        name: Field name.
        value: Field value.
        imported: True if field is imported, False for display-only.
    """
    if isinstance(value, datetime):
        value = value.isoformat()
    label = f"[green]{name}[/green]" if imported else f"[dim]{name}[/dim]"
    console.print(f"{label}: {value}")


@xml.command(
    "load",
    help=(
        "Load XML file.\n\n"
        "Parameters:\n"
        "  xml_file  Path to XML file\n\n"
        "Example:\n"
        "  xml load ./my-file.xml"
    ),
)
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--validate",
    is_flag=True,
    help="Run validation rules after loading",
)
@click.pass_obj
def xml_load(state: ShellState, xml_file: Path, validate: bool) -> None:
    """Load an MS Project XML file."""
    setup_logging(verbose=False)
    parser = MSProjectParser(str(xml_file))
    state.data = parser.parse()
    state.xml_path = xml_file
    console.print(f"[green]✓[/green] Loaded: {xml_file}")
    console.print(f"  Project: {state.data.project.name}")
    console.print(f"  Start: {state.data.project.start_date.isoformat()}")
    console.print(f"  Finish: {state.data.project.finish_date.isoformat()}")
    version = state.data.project.ms_project_save_version
    console.print(f"  MS Project Version: {version or 'unknown'}")
    milestone_count = sum(1 for task in state.data.tasks if task.is_milestone)
    console.print(f"  Tasks: {len(state.data.tasks)} ({milestone_count} milestones)")
    console.print(f"  Resources: {len(state.data.resources)}")
    console.print(f"  Assignments: {len(state.data.assignments)}")
    console.print(f"  Dependencies: {len(state.data.dependencies)}")

    if validate:
        report = validate_msproject_rules(state.data)
        _print_validation_report(report)
        if report.has_errors():
            sys.exit(2)


@xml.group(
    "list",
    help=("List XML entities.\n\nCommands:\n  tasks  List project tasks"),
)
def xml_list() -> None:
    """List entities from loaded XML."""


@xml_list.command("tasks", help="List project tasks.")
@click.option(
    "--milestones-only",
    is_flag=True,
    help="Show only milestone tasks",
)
@click.option(
    "--sort-by",
    type=click.Choice(["wbs", "start", "finish", "name"], case_sensitive=False),
    default="wbs",
    show_default=True,
    help="Sort tasks by the selected field",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def xml_list_tasks(
    state: ShellState,
    milestones_only: bool,
    sort_by: str,
    output: str,
) -> None:
    """List project tasks from loaded XML."""
    data = _require_loaded_xml(state)
    tasks = data.tasks
    if milestones_only:
        tasks = [task for task in tasks if task.is_milestone]

    if sort_by == "name":
        tasks = sorted(tasks, key=lambda t: t.name or "")
    elif sort_by == "start":
        tasks = sorted(tasks, key=lambda t: t.planned_start_date or datetime.min)
    elif sort_by == "finish":
        tasks = sorted(tasks, key=lambda t: t.planned_finish_date or datetime.min)
    else:
        tasks = sorted(tasks, key=lambda t: t.wbs_code or "")

    if output.lower() == "json":
        _print_json({"data": [task.model_dump() for task in tasks]})
        return

    if output.lower() == "csv":
        rows = []
        for task in tasks:
            rows.append(
                {
                    "id": task.uid,
                    "wbs": task.wbs_code or "",
                    "name": task.name or "",
                    "start": (
                        task.planned_start_date.isoformat()
                        if task.planned_start_date
                        else ""
                    ),
                    "finish": (
                        task.planned_finish_date.isoformat()
                        if task.planned_finish_date
                        else ""
                    ),
                    "duration": task.duration_hours or "",
                    "milestone": task.is_milestone,
                }
            )
        _print_csv(
            rows,
            [
                "id",
                "wbs",
                "name",
                "start",
                "finish",
                "duration",
                "milestone",
            ],
        )
        return

    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("WBS")
    table.add_column("Name")
    table.add_column("Start")
    table.add_column("Finish")
    table.add_column("Duration")
    table.add_column("Milestone")

    for task in tasks:
        start = task.planned_start_date
        finish = task.planned_finish_date
        table.add_row(
            str(task.uid),
            str(task.wbs_code or ""),
            str(task.name or ""),
            start.isoformat() if start else "",
            finish.isoformat() if finish else "",
            str(task.duration_hours or ""),
            "✓" if task.is_milestone else "",
        )

    console.print(table)


@xml_list.command("resources", help="List project resources.")
@click.option(
    "--output",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def xml_list_resources(state: ShellState, output: str) -> None:
    """List project resources from loaded XML."""
    data = _require_loaded_xml(state)
    resources = data.resources

    if output.lower() == "json":
        _print_json({"data": [res.model_dump() for res in resources]})
        return

    if output.lower() == "csv":
        rows = []
        for res in resources:
            rows.append(
                {
                    "id": res.uid,
                    "name": res.name or "",
                    "type": res.type.value if res.type else "",
                    "rate": res.standard_rate or "",
                }
            )
        _print_csv(rows, ["id", "name", "type", "rate"])
        return

    table = Table(title="Resources")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Rate")

    for res in resources:
        table.add_row(
            str(res.uid),
            str(res.name or ""),
            str(res.type.value if res.type else ""),
            str(res.standard_rate or ""),
        )

    console.print(table)


@xml_list.command("assignments", help="List project assignments.")
@click.option(
    "--output",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def xml_list_assignments(state: ShellState, output: str) -> None:
    """List project assignments from loaded XML."""
    data = _require_loaded_xml(state)
    assignments = data.assignments

    if output.lower() == "json":
        _print_json({"data": [assn.model_dump() for assn in assignments]})
        return

    if output.lower() == "csv":
        rows = []
        for idx, assn in enumerate(assignments, start=1):
            rows.append(
                {
                    "id": idx,
                    "task_uid": assn.task_uid,
                    "resource_uid": assn.resource_uid,
                    "work": assn.work_hours,
                }
            )
        _print_csv(rows, ["id", "task_uid", "resource_uid", "work"])
        return

    table = Table(title="Assignments")
    table.add_column("ID", style="cyan")
    table.add_column("Task")
    table.add_column("Resource")
    table.add_column("Work")

    for idx, assn in enumerate(assignments, start=1):
        table.add_row(
            str(idx),
            str(assn.task_uid),
            str(assn.resource_uid),
            str(assn.work_hours),
        )

    console.print(table)


@xml_list.command("dependencies", help="List project dependencies.")
@click.option(
    "--output",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
)
@click.pass_obj
def xml_list_dependencies(state: ShellState, output: str) -> None:
    """List project dependencies from loaded XML."""
    data = _require_loaded_xml(state)
    dependencies = data.dependencies

    if output.lower() == "json":
        _print_json({"data": [dep.model_dump() for dep in dependencies]})
        return

    if output.lower() == "csv":
        rows = []
        for idx, dep in enumerate(dependencies, start=1):
            rows.append(
                {
                    "id": idx,
                    "from_task": dep.predecessor_task_uid,
                    "to_task": dep.task_uid,
                    "type": dep.type.value if dep.type else "",
                    "lag": dep.lag,
                }
            )
        _print_csv(rows, ["id", "from_task", "to_task", "type", "lag"])
        return

    table = Table(title="Dependencies")
    table.add_column("ID", style="cyan")
    table.add_column("From Task")
    table.add_column("To Task")
    table.add_column("Type")
    table.add_column("Lag")

    for idx, dep in enumerate(dependencies, start=1):
        table.add_row(
            str(idx),
            str(dep.predecessor_task_uid),
            str(dep.task_uid),
            str(dep.type.value if dep.type else ""),
            str(dep.lag),
        )

    console.print(table)


@xml.group(
    "show",
    help=(
        "Show XML entities.\n\n"
        "Commands:\n"
        "  info  Show project information\n"
        "  task  Show task detail\n\n"
        "Example:\n"
        "  xml show task 42"
    ),
)
def xml_show() -> None:
    """Show XML entities from loaded XML."""


@xml_show.command("info", help="Show project information.")
@click.pass_obj
def xml_show_info(state: ShellState) -> None:
    """Show project information from loaded XML."""
    data = _require_loaded_xml(state)

    imported_fields = {
        "name",
        "title",
        "start_date",
        "finish_date",
        "guid",
        "ms_project_save_version",
    }
    project_data = data.project.model_dump()
    for key, value in project_data.items():
        _print_field(key, value, key in imported_fields)


@xml_show.command("task", help="Show task detail.")
@click.argument("task_id", type=int)
@click.pass_obj
def xml_show_task(state: ShellState, task_id: int) -> None:
    """Show a single task by UID."""
    data = _require_loaded_xml(state)

    imported_fields = {
        "uid",
        "guid",
        "name",
        "wbs_code",
        "is_summary",
        "is_milestone",
        "planned_start_date",
        "planned_finish_date",
        "duration_hours",
        "budget",
        "percent_complete",
        "is_critical",
        "predecessors",
    }
    display_only_fields = {
        "planned_start_date_raw",
        "planned_finish_date_raw",
        "line_number",
    }

    task = next((item for item in data.tasks if item.uid == task_id), None)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        return

    task_data = task.model_dump()
    for key, value in task_data.items():
        if key == "raw_fields":
            continue
        imported = key in imported_fields
        if key in display_only_fields:
            imported = False
        _print_field(key, value, imported)

    if task.raw_fields:
        console.print("[dim]Additional fields:[/dim]")
        for key in sorted(task.raw_fields):
            _print_field(key, task.raw_fields[key], False)


@xml_show.command("resource", help="Show resource detail.")
@click.argument("resource_id", type=int)
@click.pass_obj
def xml_show_resource(state: ShellState, resource_id: int) -> None:
    """Show a single resource by UID."""
    data = _require_loaded_xml(state)

    imported_fields = {
        "uid",
        "guid",
        "name",
        "type",
        "standard_rate",
        "max_units",
    }

    resource = next(
        (item for item in data.resources if item.uid == resource_id),
        None,
    )
    if resource is None:
        console.print(f"[red]Error:[/red] Resource not found: {resource_id}")
        return

    resource_data = resource.model_dump()
    for key, value in resource_data.items():
        if key == "raw_fields":
            continue
        _print_field(key, value, key in imported_fields)

    if resource.raw_fields:
        console.print("[dim]Additional fields:[/dim]")
        for key in sorted(resource.raw_fields):
            _print_field(key, resource.raw_fields[key], False)


@xml_show.command("assignment", help="Show assignment detail.")
@click.argument("assignment_id", type=int)
@click.pass_obj
def xml_show_assignment(state: ShellState, assignment_id: int) -> None:
    """Show a single assignment by index (1-based)."""
    data = _require_loaded_xml(state)

    imported_fields = {"task_uid", "resource_uid", "work_hours", "units"}

    assignments = data.assignments
    index = assignment_id - 1
    if index < 0 or index >= len(assignments):
        console.print(f"[red]Error:[/red] Assignment not found: {assignment_id}")
        return

    assignment = assignments[index]
    assignment_data = assignment.model_dump()
    for key, value in assignment_data.items():
        if key == "raw_fields":
            continue
        _print_field(key, value, key in imported_fields)

    if assignment.raw_fields:
        console.print("[dim]Additional fields:[/dim]")
        for key in sorted(assignment.raw_fields):
            _print_field(key, assignment.raw_fields[key], False)


@xml_show.command("dependency", help="Show dependency detail.")
@click.argument("dependency_id", type=int)
@click.pass_obj
def xml_show_dependency(state: ShellState, dependency_id: int) -> None:
    """Show a single dependency by index (1-based)."""
    data = _require_loaded_xml(state)

    imported_fields = {
        "task_uid",
        "predecessor_task_uid",
        "type",
        "lag",
    }

    dependencies = data.dependencies
    index = dependency_id - 1
    if index < 0 or index >= len(dependencies):
        console.print(f"[red]Error:[/red] Dependency not found: {dependency_id}")
        return

    dependency = dependencies[index]
    dependency_data = dependency.model_dump()
    for key, value in dependency_data.items():
        if key == "raw_fields":
            continue
        _print_field(key, value, key in imported_fields)

    if dependency.raw_fields:
        console.print("[dim]Additional fields:[/dim]")
        for key in sorted(dependency.raw_fields):
            _print_field(key, dependency.raw_fields[key], False)


@xml.command("validate", help="Validate loaded XML data.")
@click.option(
    "--output",
    type=click.Choice(["console", "table", "json", "html"], case_sensitive=False),
    default="console",
    show_default=True,
    help="Output format",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors",
)
@click.pass_obj
def xml_validate(state: ShellState, output: str, strict: bool) -> None:
    """Validate XML data using built-in rules."""
    data = _require_loaded_xml(state)

    setup_logging(verbose=False)
    report = validate_msproject_rules(data, strict=strict)
    payload = report.model_dump()

    if output.lower() == "console":
        console.print("Running validation checks...\n")
        if not report.checks:
            console.print("[green]✓[/green] Validation passed")
        for issue in report.checks:
            severity = issue.severity.value.upper()
            line_info = f" (line {issue.line})" if issue.line else ""
            console.print(f"{severity}: {issue.message}{line_info}")
        console.print(
            "\nValidation completed: "
            f"{report.summary.get('errors', 0)} errors, "
            f"{report.summary.get('warnings', 0)} warnings"
        )
        if report.has_errors():
            sys.exit(2)
        return

    if output.lower() == "json":
        console.print_json(json.dumps(payload))
        if report.has_errors():
            sys.exit(2)
        return

    if output.lower() == "html":
        sys.stdout.write(_render_validation_html(report))
        if report.has_errors():
            sys.exit(2)
        return

    table = Table(title="Validation Report")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Message")
    table.add_column("Line")

    for issue in report.checks:
        severity = issue.severity.value.upper()
        table.add_row(
            severity,
            issue.id,
            issue.message,
            str(issue.line or ""),
        )

    console.print(table)
    summary = report.summary
    console.print(
        "Validation summary: "
        f"{summary.get('errors', 0)} errors, "
        f"{summary.get('warnings', 0)} warnings"
    )

    if report.has_errors():
        sys.exit(2)


@xml.group(
    "import",
    help=(
        "Import XML entities.\n\n"
        "Commands:\n"
        "  create-project  Create a project and import data\n"
        "  project         Import full project\n"
        "  task            Import a single task"
    ),
)
def xml_import() -> None:
    """Import entities into wfp-poc."""


def _print_validation_report(report: ValidationReport) -> None:
    """Print a concise validation summary.

    Args:
        report: Validation report from validate_msproject_rules.
    """
    summary = report.summary
    console.print(
        "Validation summary: "
        f"{summary.get('errors', 0)} errors, "
        f"{summary.get('warnings', 0)} warnings"
    )


def _print_rollback_failures(failures: list[dict[str, str]]) -> None:
    """Print rollback failures.

    Args:
        failures: Failure entries from rollback.
    """
    if not failures:
        return
    console.print("[yellow]Rollback issues:[/yellow]")
    for failure in failures:
        console.print(f"  • {failure}")


@xml_import.command(
    "create-project",
    help="Create a new project from loaded XML and import data.",
)
@click.option("--dry-run", is_flag=True, help="Validate without API calls")
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue importing remaining entities if one fails",
)
@click.option(
    "--token",
    type=str,
    envvar="WFP_JWT_TOKEN",
    help="JWT authentication token (or set WFP_JWT_TOKEN env var)",
)
@click.option(
    "--env",
    "env_name",
    type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
    help="Environment to load (.env.dev/.env.staging/.env.prod)",
)
@click.option(
    "--api-url",
    type=str,
    envvar="WFP_API_URL",
    default="http://localhost:5000",
    help="wfp-poc API base URL (or set WFP_API_URL env var)",
)
@click.option(
    "--company-id",
    type=str,
    help="Company UUID for multi-tenant isolation (optional)",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["debug", "info", "warning", "error", "critical"],
        case_sensitive=False,
    ),
    help="Logging level",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
@click.pass_obj
def xml_import_create_project(
    state: ShellState,
    dry_run: bool,
    continue_on_error: bool,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Create a new project from loaded XML and import entities."""
    data = _require_loaded_xml(state)
    setup_logging(verbose, log_level)

    console.print("\n[bold]Validating data...[/bold]")
    report = validate_msproject_rules(data)
    _print_validation_report(report)
    if report.has_errors():
        sys.exit(2)

    if dry_run:
        console.print("[yellow]Dry run:[/yellow] Skipping API calls")
        return

    client = _build_client(api_url, token, company_id, env_name)
    start_time = time.monotonic()

    console.print("\n[bold]Creating project...[/bold]")
    try:
        project_result = client.create_project(data.project)
        project_id = _extract_project_id(project_result)
    except (WfpApiError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(1)

    state.selected_project_id = project_id
    console.print(f"[green]✓[/green] Project created: {project_id}")

    try:
        _import_project_entities(
            client,
            project_id,
            data,
            continue_on_error,
        )
    except SystemExit:
        try:
            client._request("DELETE", f"/v0/projects/{project_id}")
        except WfpApiError as delete_exc:
            console.print(
                "[yellow]Warning:[/yellow] "
                "Unable to delete project after rollback: "
                f"{redact_secrets(str(delete_exc))}"
            )
        raise

    duration = time.monotonic() - start_time
    console.print("\n[green]✓[/green] Import completed successfully")
    console.print(f"Duration: {int(duration // 60)}m {int(duration % 60)}s")


@xml_import.command("project", help="Import full project data.")
@click.option("--dry-run", is_flag=True, help="Validate without API calls")
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue importing remaining entities if one fails",
)
@click.option(
    "--token",
    type=str,
    envvar="WFP_JWT_TOKEN",
    help="JWT authentication token (or set WFP_JWT_TOKEN env var)",
)
@click.option(
    "--env",
    "env_name",
    type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
    help="Environment to load (.env.dev/.env.staging/.env.prod)",
)
@click.option(
    "--api-url",
    type=str,
    envvar="WFP_API_URL",
    default="http://localhost:5000",
    help="wfp-poc API base URL (or set WFP_API_URL env var)",
)
@click.option(
    "--company-id",
    type=str,
    help="Company UUID for multi-tenant isolation (optional)",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["debug", "info", "warning", "error", "critical"],
        case_sensitive=False,
    ),
    help="Logging level",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
@click.pass_obj
def xml_import_project(
    state: ShellState,
    dry_run: bool,
    continue_on_error: bool,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Import full project data from loaded XML."""
    data = _require_loaded_xml(state)
    setup_logging(verbose, log_level)
    project_id = _require_selected_project(state)

    console.print("\n[bold]Validating data...[/bold]")
    report = validate_msproject_rules(data)
    _print_validation_report(report)
    if report.has_errors():
        sys.exit(2)

    if dry_run:
        console.print("[yellow]Dry run:[/yellow] Skipping API calls")
        return

    client = _build_client(api_url, token, company_id, env_name)
    start_time = time.monotonic()

    _import_project_entities(
        client,
        project_id,
        data,
        continue_on_error,
    )

    duration = time.monotonic() - start_time
    console.print("\n[green]✓[/green] Import completed successfully")
    console.print(f"Duration: {int(duration // 60)}m {int(duration % 60)}s")


@xml_import.command("task", help="Import a single task by UID.")
@click.argument("task_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate without API calls")
@click.option(
    "--with-dependencies",
    is_flag=True,
    help="Also import task dependencies",
)
@click.option(
    "--with-assignments",
    is_flag=True,
    help="Also import task assignments",
)
@click.option(
    "--token",
    type=str,
    envvar="WFP_JWT_TOKEN",
    help="JWT authentication token (or set WFP_JWT_TOKEN env var)",
)
@click.option(
    "--env",
    "env_name",
    type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
    help="Environment to load (.env.dev/.env.staging/.env.prod)",
)
@click.option(
    "--api-url",
    type=str,
    envvar="WFP_API_URL",
    default="http://localhost:5000",
    help="wfp-poc API base URL (or set WFP_API_URL env var)",
)
@click.option(
    "--company-id",
    type=str,
    help="Company UUID for multi-tenant isolation (optional)",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["debug", "info", "warning", "error", "critical"],
        case_sensitive=False,
    ),
    help="Logging level",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
@click.pass_obj
def xml_import_task(
    state: ShellState,
    task_id: int,
    dry_run: bool,
    with_dependencies: bool,
    with_assignments: bool,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Import a single task for debugging."""
    data = _require_loaded_xml(state)
    setup_logging(verbose, log_level)
    project_id = _require_selected_project(state)

    task = next((item for item in data.tasks if item.uid == task_id), None)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        sys.exit(1)

    task_assignments = [assn for assn in data.assignments if assn.task_uid == task.uid]
    needed_resource_uids = {assn.resource_uid for assn in task_assignments}
    task_resources = [
        resource for resource in data.resources if resource.uid in needed_resource_uids
    ]
    task_dependencies = [
        dep
        for dep in data.dependencies
        if dep.task_uid == task.uid or dep.predecessor_task_uid == task.uid
    ]
    validation_data = MSProjectData(
        project=data.project,
        tasks=[task],
        dependencies=task_dependencies,
        resources=task_resources,
        assignments=task_assignments,
    )

    console.print("\n[bold]Validating task...[/bold]")
    report = validate_msproject_rules(validation_data)
    _print_validation_report(report)
    if report.has_errors():
        sys.exit(2)

    if dry_run:
        console.print("[yellow]Dry run:[/yellow] Skipping API calls")
        return

    client = _build_client(api_url, token, company_id, env_name)

    created_task_ids: list[str] = []
    created_resource_ids: list[str] = []
    created_assignment_ids: list[str] = []
    task_map: dict[int, str] = {}
    resource_map: dict[int, str] = {}

    try:
        result = client.create_task(project_id, task)
        task_id_value = result.get("task_id")
        task_map.update(result.get("task_map", {}))
        if task_id_value:
            created_task_ids.append(task_id_value)
        console.print("[green]✓[/green] Task created successfully")
        if task_id_value:
            console.print(f"  UUID: {task_id_value}")

        if with_assignments:
            for resource in task_resources:
                if resource.uid not in needed_resource_uids:
                    continue
                res_result = client.create_resource(resource)
                resource_id = res_result.get("resource_id")
                resource_map.update(res_result.get("resource_map", {}))
                if resource_id:
                    created_resource_ids.append(resource_id)

            for assignment in task_assignments:
                assn_result = client.create_assignment(
                    project_id,
                    assignment,
                    task_map,
                    resource_map,
                )
                assignment_id = assn_result.get("assignment_id")
                if assignment_id:
                    created_assignment_ids.append(assignment_id)

        if with_dependencies:
            client.sync_tasks(project_id, [task])
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        console.print("[red]✗ Import failed. Rolling back...[/red]")
        rollback = client.rollback_import(
            project_id,
            task_ids=created_task_ids,
            assignment_ids=created_assignment_ids,
            resource_ids=created_resource_ids,
        )
        _print_rollback_failures(rollback.get("failed", []))
        sys.exit(1)

    if not with_dependencies:
        console.print("Dependencies skipped (use --with-dependencies to include)")
    if not with_assignments:
        console.print("Assignments skipped (use --with-assignments to include)")
