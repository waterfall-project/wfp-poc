# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Commands for interacting with the wfp-poc service."""

import logging
import sys
import time
import uuid

import click

from poc_import.api.client import WfpApiClient, WfpApiError
from poc_import.cli_support import (
    console,
    log_duration,
    redact_secrets,
    set_correlation_id,
    setup_logging,
)
from poc_import.config import Config, load_env_file


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


@click.group(
    help=(
        "Manipulating the wfp-poc service.\n\n"
        "Commands:\n"
        "  projects  Manage projects (see help service projects)\n"
        "  tasks     Manage tasks (see help service tasks)"
    )
)
def service() -> None:
    """Service-related commands."""


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
