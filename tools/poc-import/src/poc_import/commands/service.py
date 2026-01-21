# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Commands for interacting with the wfp-poc service."""

import json
import logging
import sys
import time
import uuid
from collections.abc import Callable
from typing import Any

import click
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
from poc_import.shell_state import ShellState


def _build_client(
    api_url: str,
    token: str | None,
    company_id: str | None,
    env_name: str | None,
) -> WfpApiClient:
    """Build API client with configuration and token handling."""
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


def _require_selected_project(state: ShellState) -> str:
    """Return selected project ID or exit with a helpful error."""
    if not state.selected_project_id:
        console.print(
            "[red]Error:[/red] No project selected. "
            "Use 'service select <project_id>' first."
        )
        sys.exit(1)
    return state.selected_project_id


def _output_json(data: dict[str, Any]) -> None:
    """Print JSON output using the rich console."""
    console.print_json(json.dumps(data))


def _print_kv(data: dict[str, Any]) -> None:
    """Print key-value pairs to console."""
    for key, value in data.items():
        console.print(f"{key}: {value}")


def _matches_id(value: Any, target: str) -> bool:
    """Return True when value matches target ID as string."""
    if value is None:
        return False
    return str(value) == str(target)


def _filter_assignments_for_task(
    items: list[dict[str, Any]],
    task_id: str,
) -> list[dict[str, Any]]:
    """Filter assignments for a given task ID."""
    return [item for item in items if _matches_id(item.get("task_id"), task_id)]


def _filter_assignments_for_resource(
    items: list[dict[str, Any]],
    resource_id: str,
) -> list[dict[str, Any]]:
    """Filter assignments for a given resource ID."""
    return [item for item in items if _matches_id(item.get("resource_id"), resource_id)]


def _filter_dependencies_for_task(
    items: list[dict[str, Any]],
    task_id: str,
) -> list[dict[str, Any]]:
    """Filter dependencies where task is predecessor or successor."""
    return [
        item
        for item in items
        if _matches_id(item.get("task_id"), task_id)
        or _matches_id(item.get("successor_task_id"), task_id)
        or _matches_id(item.get("predecessor_task_id"), task_id)
    ]


def _collect_paginated(
    fetch_page: Callable[[int, int], dict[str, Any]],
    per_page: int = 100,
) -> list[dict[str, Any]]:
    """Collect all items from a paginated API endpoint.

    Args:
        fetch_page: Function that fetches a page given (page, per_page).
        per_page: Page size to request.

    Returns:
        List of aggregated items.
    """
    items: list[dict[str, Any]] = []
    page = 1

    while True:
        result = fetch_page(page, per_page)
        page_items = result.get("data", [])
        if isinstance(page_items, list):
            items.extend(page_items)

        total_pages = result.get("total_pages")
        if isinstance(total_pages, int):
            if page >= total_pages:
                break
            page += 1
            continue

        if not page_items or len(page_items) < per_page:
            break
        page += 1

    return items


def _print_assignments_table(assignments: list[dict[str, Any]]) -> None:
    """Print assignments table."""
    if not assignments:
        console.print("No assignments found.")
        return

    table = Table(title="Assignments")
    table.add_column("ID", style="cyan")
    table.add_column("Task ID")
    table.add_column("Resource ID")
    table.add_column("Work")

    for item in assignments:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("task_id", "")),
            str(item.get("resource_id", "")),
            str(item.get("work_hours", item.get("work", ""))),
        )

    console.print(table)


def _print_dependencies_table(dependencies: list[dict[str, Any]]) -> None:
    """Print dependencies table."""
    if not dependencies:
        console.print("No dependencies found.")
        return

    table = Table(title="Dependencies")
    table.add_column("ID", style="cyan")
    table.add_column("Predecessor")
    table.add_column("Successor")
    table.add_column("Type")
    table.add_column("Lag")

    for item in dependencies:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("predecessor_task_id", "")),
            str(item.get("task_id", item.get("successor_task_id", ""))),
            str(item.get("type", "")),
            str(item.get("lag", "")),
        )

    console.print(table)


@click.group(
    help=(
        "Manipulating the wfp-poc service.\n\n"
        "Commands:\n"
        "  list    List service entities (see help service list)\n"
        "  show    Show service entities (see help service show)\n"
        "  select  Select active project context\n"
        "  delete  Delete service entities (see help service delete)"
    )
)
def service() -> None:
    """Service-related commands."""


@service.command(
    "select",
    help=(
        "Select active project context.\n\n"
        "Parameters:\n"
        "  project_id  Project UUID\n\n"
        "Example:\n"
        "  service select <project_id>"
    ),
)
@click.argument("project_id")
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
    "verbose",
    is_flag=True,
    help="Enable verbose logging",
)
@click.pass_obj
def service_select(
    state: ShellState,
    project_id: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Select active project context from the API."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        project = client.get_project(project_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    project_data = project.get("data", project)
    state.selected_project_id = project_data.get("id", project_id)
    state.selected_project_name = project_data.get("name")
    task_count = project_data.get("task_count")
    console.print(
        "[green]\u2713[/green] Project selected: "
        f"{state.selected_project_name or state.selected_project_id}"
        + (f" ({task_count} tasks)" if task_count is not None else "")
    )

    log_duration(start_time, "service select", logger)


@service.group(
    "list",
    help=(
        "List service entities.\n\n"
        "Commands:\n"
        "  projects     List projects\n"
        "  tasks        List tasks for selected project\n"
        "  resources    List resources\n"
        "  assignments  List assignments for selected project\n"
        "  dependencies  List dependencies for selected project"
    ),
)
def service_list() -> None:
    """List service entities."""


@service.group(
    "delete",
    help=(
        "Delete service entities.\n\n"
        "Commands:\n"
        "  project     Delete selected project (or pass project_id)\n"
        "  task        Delete task by ID (selected project required)\n"
        "  resource    Delete resource by ID\n"
        "  assignment  Delete assignment by ID (selected project required)"
    ),
)
def service_delete() -> None:
    """Delete service entities."""


@service_list.command("projects", help="List projects.")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_list_projects(
    page: int | None,
    per_page: int | None,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List projects from the API."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_projects(page=page, per_page=per_page)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    if output.lower() == "json":
        _output_json(result)
        return

    items = result.get("data", [])
    if not items:
        console.print("No projects found.")
        return

    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Start Date")
    table.add_column("End Date")
    table.add_column("Task Count", justify="right")

    for item in items:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("start_date", "")),
            str(item.get("finish_date", "")),
            str(item.get("task_count", "")),
        )

    console.print(table)
    log_duration(start_time, "service list projects", logger)


@service_list.command("tasks", help="List tasks for the selected project.")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_list_tasks(
    state: ShellState,
    page: int | None,
    per_page: int | None,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List tasks for the selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_project_tasks(
            project_id=project_id, page=page, per_page=per_page
        )
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    if output.lower() == "json":
        _output_json(result)
        return

    items = result.get("data", [])
    if not items:
        console.print("No tasks found.")
        return

    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Start")
    table.add_column("Finish")
    table.add_column("WBS")

    for item in items:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("start", "")),
            str(item.get("finish", "")),
            str(item.get("wbs", "")),
        )

    console.print(table)
    log_duration(start_time, "service list tasks", logger)


@service_list.command("resources", help="List resources.")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_list_resources(
    state: ShellState,
    page: int | None,
    per_page: int | None,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List resources."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_resources(page=page, per_page=per_page)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    if output.lower() == "json":
        _output_json(result)
        return

    items = result.get("data", [])
    if not items:
        console.print("No resources found.")
        return

    table = Table(title="Resources")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Rate")

    for item in items:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("type", "")),
            str(item.get("standard_rate", "")),
        )

    console.print(table)
    log_duration(start_time, "service list resources", logger)


@service_list.command("assignments", help="List assignments for project.")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_list_assignments(
    state: ShellState,
    page: int | None,
    per_page: int | None,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List assignments for the selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_assignments(
            project_id=project_id, page=page, per_page=per_page
        )
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    if output.lower() == "json":
        _output_json(result)
        return

    items = result.get("data", [])
    if not items:
        console.print("No assignments found.")
        return

    table = Table(title="Assignments")
    table.add_column("ID", style="cyan")
    table.add_column("Task ID")
    table.add_column("Resource ID")
    table.add_column("Work")

    for item in items:
        table.add_row(
            str(item.get("id", "")),
            str(item.get("task_id", "")),
            str(item.get("resource_id", "")),
            str(item.get("work", "")),
        )

    console.print(table)
    log_duration(start_time, "service list assignments", logger)


@service_list.command("dependencies", help="List dependencies for project.")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_list_dependencies(
    state: ShellState,
    page: int | None,
    per_page: int | None,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List dependencies for the selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_project_tasks(
            project_id=project_id,
            page=page,
            per_page=per_page,
        )
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    task_items = result.get("data", [])
    dependencies: list[dict[str, object]] = []
    for task in task_items:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        predecessors = task.get("predecessors") or []
        for pred in predecessors:
            if not isinstance(pred, dict):
                continue
            dependencies.append(
                {
                    "from_task_id": pred.get("predecessor_task_id"),
                    "to_task_id": task_id,
                    "type": pred.get("type"),
                    "lag": pred.get("lag"),
                }
            )

    if output.lower() == "json":
        _output_json({"data": dependencies})
        return

    if not dependencies:
        console.print("No dependencies found.")
        return

    table = Table(title="Dependencies")
    table.add_column("ID", style="cyan")
    table.add_column("From Task")
    table.add_column("To Task")
    table.add_column("Type")
    table.add_column("Lag")

    for idx, item in enumerate(dependencies, start=1):
        table.add_row(
            str(idx),
            str(item.get("from_task_id", "")),
            str(item.get("to_task_id", "")),
            str(item.get("type", "")),
            str(item.get("lag", "")),
        )

    console.print(table)
    log_duration(start_time, "service list dependencies", logger)


@service_delete.command("project", help="Delete a project.")
@click.argument("project_id", required=False)
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
def service_delete_project(
    state: ShellState,
    project_id: str | None,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Delete a project by ID or selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()

    if not project_id:
        if not state.selected_project_id:
            console.print(
                "[red]Error:[/red] No project selected. "
                "Use `service select <project_id>` or pass project_id."
            )
            sys.exit(1)
        project_id = state.selected_project_id

    client = _build_client(api_url, token, company_id, env_name)

    try:
        console.print("[bold]Deleting project dependencies...[/bold]")

        expenses = _collect_paginated(
            lambda page, per_page: client.list_project_expenses(
                project_id,
                page=page,
                per_page=per_page,
            )
        )
        for expense in expenses:
            expense_id = expense.get("id")
            if expense_id:
                client.delete_expense(project_id, str(expense_id))

        assignments = _collect_paginated(
            lambda page, per_page: client.list_assignments(
                project_id,
                page=page,
                per_page=per_page,
            )
        )
        for assignment in assignments:
            assignment_id = assignment.get("id")
            if assignment_id:
                client.delete_assignment(project_id, str(assignment_id))

        tasks = _collect_paginated(
            lambda page, per_page: client.list_project_tasks(
                project_id,
                page=page,
                per_page=per_page,
            )
        )
        for task in tasks:
            task_id = task.get("id")
            if task_id:
                client.delete_task(project_id, str(task_id))

        milestones = _collect_paginated(
            lambda page, per_page: client.list_project_milestones(
                project_id,
                page=page,
                per_page=per_page,
            )
        )
        for milestone in milestones:
            milestone_id = milestone.get("id")
            if milestone_id:
                client.delete_milestone(project_id, str(milestone_id))

        client.delete_project(project_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    console.print(f"[green]✓[/green] Project deleted: {project_id}")
    if state.selected_project_id == project_id:
        state.selected_project_id = None
        state.selected_project_name = None
    log_duration(start_time, "service delete project", logger)


@service_delete.command("task", help="Delete a task by ID.")
@click.argument("task_id")
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
def service_delete_task(
    state: ShellState,
    task_id: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Delete a task for the selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        client.delete_task(project_id, task_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    console.print(f"[green]✓[/green] Task deleted: {task_id}")
    log_duration(start_time, "service delete task", logger)


@service_delete.command("resource", help="Delete a resource by ID.")
@click.argument("resource_id")
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
def service_delete_resource(
    state: ShellState,
    resource_id: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Delete a resource by ID."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        client.delete_resource(resource_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    console.print(f"[green]✓[/green] Resource deleted: {resource_id}")
    log_duration(start_time, "service delete resource", logger)


@service_delete.command("assignment", help="Delete an assignment by ID.")
@click.argument("assignment_id")
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
def service_delete_assignment(
    state: ShellState,
    assignment_id: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Delete an assignment for the selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        client.delete_assignment(project_id, assignment_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    console.print(f"[green]✓[/green] Assignment deleted: {assignment_id}")
    log_duration(start_time, "service delete assignment", logger)


@service.group(
    "show",
    help=(
        "Show service entities.\n\n"
        "Commands:\n"
        "  project     Show selected project\n"
        "  task        Show task by ID\n"
        "  resource    Show resource by ID\n"
        "  assignment  Show assignment by ID\n"
        "  dependency  Show dependency by ID"
    ),
)
def service_show() -> None:
    """Show service entities."""


@service_show.command("project", help="Show selected project details.")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_show_project(
    state: ShellState,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Show selected project details."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.get_project(project_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    data = result.get("data", result)
    if output.lower() == "json":
        _output_json({"data": data})
        return

    _print_kv(data)
    log_duration(start_time, "service show project", logger)


@service_show.command("task", help="Show task by ID.")
@click.argument("task_id")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_show_task(
    state: ShellState,
    task_id: str,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Show task details for selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.get_project_task(project_id, task_id)
        assignments_result = client.list_assignments(project_id=project_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    data = result.get("data", result)
    assignments = _filter_assignments_for_task(
        assignments_result.get("data", []), task_id
    )
    predecessors = data.get("predecessors", []) if isinstance(data, dict) else []
    dependencies = []
    for pred in predecessors:
        if not isinstance(pred, dict):
            continue
        dependencies.append(
            {
                "predecessor_task_id": pred.get("predecessor_task_id"),
                "successor_task_id": task_id,
                "type": pred.get("type"),
                "lag": pred.get("lag"),
            }
        )
    if output.lower() == "json":
        _output_json(
            {
                "data": data,
                "assignments": assignments,
                "dependencies": dependencies,
            }
        )
        return

    _print_kv(data)
    console.print()
    console.print("Assignments:")
    _print_assignments_table(assignments)
    console.print()
    console.print("Dependencies:")
    _print_dependencies_table(dependencies)
    log_duration(start_time, "service show task", logger)


@service_show.command("resource", help="Show resource by ID.")
@click.argument("resource_id")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_show_resource(
    state: ShellState,
    resource_id: str,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Show resource details."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.get_resource(resource_id)
        assignments_result = client.list_assignments(project_id=project_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    data = result.get("data", result)
    assignments = _filter_assignments_for_resource(
        assignments_result.get("data", []), resource_id
    )
    if output.lower() == "json":
        _output_json({"data": data, "assignments": assignments})
        return

    _print_kv(data)
    console.print()
    console.print("Assignments:")
    _print_assignments_table(assignments)
    log_duration(start_time, "service show resource", logger)


@service_show.command("assignment", help="Show assignment by ID.")
@click.argument("assignment_id")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_show_assignment(
    state: ShellState,
    assignment_id: str,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Show assignment details for selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    project_id = _require_selected_project(state)
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.get_assignment(project_id, assignment_id)
    except WfpApiError as exc:
        console.print(f"[red]Error:[/red] {redact_secrets(str(exc))}")
        sys.exit(2)

    data = result.get("data", result)
    if output.lower() == "json":
        _output_json({"data": data})
        return

    _print_kv(data)
    log_duration(start_time, "service show assignment", logger)


@service_show.command("dependency", help="Show dependency by ID.")
@click.argument("dependency_id")
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format",
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
def service_show_dependency(
    state: ShellState,
    dependency_id: str,
    output: str,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Show dependency details for selected project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    _require_selected_project(state)
    load_env_file(env_name)

    message = (
        "Dependency endpoints are not available in the API. "
        "Use `service list tasks` to inspect task predecessors."
    )

    if output.lower() == "json":
        _output_json(
            {
                "error": message,
                "dependency_id": dependency_id,
            }
        )
        sys.exit(2)

    console.print(f"[red]Error:[/red] {message}")
    console.print(f"Dependency ID: {dependency_id}")
    sys.exit(2)
    log_duration(start_time, "service show dependency", logger)


@service.group(
    "projects",
    help=("Project operations.\n\nCommands:\n  list  List projects"),
)
def service_projects() -> None:
    """Project operations."""


@service_projects.command(
    "list",
    help=(
        "List projects.\n\n"
        "Parameters:\n"
        "  --page      Page number\n"
        "  --per-page  Items per page\n\n"
        "Example:\n"
        "  service projects list --page 1 --per-page 25"
    ),
)
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
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
        ["debug", "info", "warning", "error", "critical"], case_sensitive=False
    ),
    help="Logging level",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def service_projects_list(
    page: int | None,
    per_page: int | None,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List projects from the API."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_projects(page=page, per_page=per_page)
    except WfpApiError as e:
        console.print(f"[red]Error:[/red] {redact_secrets(str(e))}")
        sys.exit(2)

    items = result.get("data", [])
    if not items:
        console.print("No projects found.")
        return

    for item in items:
        project_id = item.get("id")
        name = item.get("name")
        code = item.get("code")
        console.print(f"- {project_id} | {name} | {code}")

    log_duration(start_time, "service projects list", logger)


@service.group(
    "tasks",
    help=("Task operations.\n\nCommands:\n  list  List tasks for a project"),
)
def service_tasks() -> None:
    """Task operations."""


@service_tasks.command(
    "list",
    help=(
        "List tasks for a project.\n\n"
        "Parameters:\n"
        "  project_id  Project UUID\n"
        "  --page      Page number\n"
        "  --per-page  Items per page\n\n"
        "Example:\n"
        "  service tasks list <project_id> --page 1 --per-page 25"
    ),
)
@click.argument("project_id")
@click.option("--page", type=int, help="Page number")
@click.option("--per-page", type=int, help="Items per page")
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
        ["debug", "info", "warning", "error", "critical"], case_sensitive=False
    ),
    help="Logging level",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def service_tasks_list(
    project_id: str,
    page: int | None,
    per_page: int | None,
    token: str | None,
    env_name: str | None,
    api_url: str,
    company_id: str | None,
    log_level: str | None,
    verbose: bool,
) -> None:
    """List tasks for a project."""
    setup_logging(verbose, log_level)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    client = _build_client(api_url, token, company_id, env_name)

    try:
        result = client.list_project_tasks(
            project_id=project_id,
            page=page,
            per_page=per_page,
        )
    except WfpApiError as e:
        console.print(f"[red]Error:[/red] {redact_secrets(str(e))}")
        sys.exit(2)

    items = result.get("data", [])
    if not items:
        console.print("No tasks found.")
        return

    for item in items:
        task_id = item.get("id")
        name = item.get("name")
        wbs = item.get("wbs") or ""
        console.print(f"- {task_id} | {name} | {wbs}")

    log_duration(start_time, "service tasks list", logger)
