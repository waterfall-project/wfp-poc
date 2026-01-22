# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""MS Project XML import command."""

import logging
import sys
import time
import uuid
from pathlib import Path

import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from poc_import.api.client import WfpApiClient, WfpApiError
from poc_import.cli_support import (
    console,
    log_duration,
    redact_secrets,
    set_correlation_id,
    setup_logging,
)
from poc_import.config import Config, load_env_file
from poc_import.models import ImportMode, ImportReport
from poc_import.parsers.msproject import MSProjectParser, MSProjectParserError
from poc_import.validators import (
    ValidationError,
    validate_for_initial_import,
    validate_for_sync_import,
)


@click.command(help="Import MS Project XML file into the API.")
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--mode",
    type=click.Choice(["initial", "sync"]),
    required=True,
    help="Import mode: initial (create) or sync (update)",
)
@click.option(
    "--project-id",
    type=str,
    help="Existing project UUID (required for sync mode)",
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
    help="JWT authentication token (or set WFP_JWT_TOKEN env var)",
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
    "--dry-run",
    is_flag=True,
    help="Validate only, do not call API",
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
@click.option(
    "--output-report",
    type=click.Path(path_type=Path),
    help="Save import report to JSON file",
)
def msproject(
    xml_file: Path,
    mode: str,
    project_id: str | None,
    env_name: str | None,
    token: str | None,
    api_url: str,
    company_id: str | None,
    dry_run: bool,
    log_level: str | None,
    verbose: bool,
    output_report: Path | None,
) -> None:
    """Import MS Project XML file.

    Example usage:

        \b
        # Initial import
        poc-import msproject planning.xml --mode=initial --token=$TOKEN

        \b
        # Sync mode (update)
        poc-import msproject planning.xml --mode=sync --project-id=<uuid> --token=$TOKEN

        \b
        # Dry run (validation only)
        poc-import msproject planning.xml --mode=initial --token=$TOKEN --dry-run
    """
    setup_logging(verbose, log_level)
    load_env_file(env_name)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    config = Config()

    api_url = api_url or config.api_url
    company_id = company_id or config.company_id

    # Generate correlation ID for tracing
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    logger.info("Starting import")

    # Validate arguments
    if mode == "sync" and not project_id:
        console.print("[red]Error:[/red] --project-id is required for sync mode")
        sys.exit(1)

    if not token:
        token = config.jwt_token
    if not token and not dry_run:
        token = config.build_jwt_token()
    if not dry_run and not token:
        console.print(
            "[red]Error:[/red] --token is required (or set WFP_JWT_TOKEN env var)"
        )
        console.print(
            "[yellow]Tip:[/yellow] Set JWT_SECRET_KEY + WFP_USER_ID/WFP_COMPANY_ID "
            "in tools/poc-import/.env to auto-generate a token."
        )
        sys.exit(1)

    # Parse MS Project XML
    try:
        console.print(f"\n[bold]Parsing MS Project file:[/bold] {xml_file}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Parsing XML...", total=None)

            parser = MSProjectParser(str(xml_file))
            data = parser.parse()

            progress.update(task, completed=True)

        # Display summary
        console.print("\n[green]✓[/green] Parsed successfully:")
        console.print(f"  Project: {data.project.name}")
        console.print(f"  Tasks: {len(data.tasks)}")
        console.print(f"  Milestones: {sum(1 for t in data.tasks if t.is_milestone)}")
        console.print(f"  Resources: {len(data.resources)}")
        console.print(f"  Assignments: {len(data.assignments)}")

        # Validate parsed data
        console.print("\n[bold]Validating data...[/bold]")
        try:
            if mode == "initial":
                validate_for_initial_import(data)
                console.print("[green]✓[/green] Validation passed")
            else:  # sync mode
                # For sync, we need existing milestones from API
                # We'll validate after fetching them
                console.print("[yellow]⚠[/yellow] Full validation after API connection")
        except ValidationError as e:
            console.print("\n[red]✗ Validation failed:[/red]")
            for error in e.errors:
                console.print(f"  • {error.get('error', error)}")
            sys.exit(1)

        if dry_run:
            console.print("\n[yellow]Dry run mode:[/yellow] Skipping API calls")
            console.print("[green]✓[/green] Validation passed")
            sys.exit(0)

        # Initialize API client
        console.print("\n[bold]Connecting to wfp-poc API...[/bold]")
        console.print(f"  URL: {api_url}")

        # token is guaranteed to be non-None here (checked above when not dry_run)
        assert token is not None

        client = WfpApiClient(
            base_url=api_url,
            token=token,
            correlation_id=correlation_id,
            company_id=company_id,
        )

        # Validate token
        try:
            client.validate_token()
            console.print("[green]✓[/green] Authentication successful")
        except WfpApiError as e:
            console.print(
                f"\n[red]✗ Authentication failed:[/red] {redact_secrets(str(e))}"
            )
            if e.status_code == 401:
                console.print("  Check your JWT token and try again")
            sys.exit(2)

        # Perform import
        try:
            if mode == "initial":
                console.print("\n[bold]Creating new project...[/bold]")
                project_result = client.create_project(data.project)
                actual_project_id = project_result["id"]
                console.print(f"[green]✓[/green] Project created: {actual_project_id}")

                console.print(
                    "\n[bold]Importing tasks (resources and assignments are "
                    "company-scoped)...[/bold]"
                )
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Importing...", total=None)

                    import_summary = client.import_msproject_data(
                        actual_project_id, data, mode="initial"
                    )

                    progress.update(task, completed=True)

                console.print("\n[green]✓[/green] Initial import completed:")
                console.print(f"  Tasks created: {import_summary['tasks_created']}")
                console.print("  Resources created: 0 (skipped)")
                console.print("  Assignments created: 0 (skipped)")

                if import_summary["tasks_failed"] > 0:
                    console.print(
                        f"  [yellow]⚠ Tasks failed: "
                        f"{import_summary['tasks_failed']}[/yellow]"
                    )

                if import_summary["failed_batches"]:
                    console.print(
                        f"\n[yellow]⚠ "
                        f"{len(import_summary['failed_batches'])} "
                        f"batch(es) failed[/yellow]"
                    )
                    for fb in import_summary["failed_batches"]:
                        console.print(
                            f"  • {fb['batch_type']} batch "
                            f"{fb.get('batch_num', 'N/A')}: {fb['error']}"
                        )

                # Create success report
                report = ImportReport(
                    correlation_id=correlation_id,
                    mode=ImportMode.INITIAL,
                    success=True,
                    project_id=actual_project_id,
                    created_count=import_summary["tasks_created"],
                )

            else:  # sync mode
                # project_id is guaranteed to be non-None here
                # (checked above for sync mode)
                assert project_id is not None

                console.print(
                    f"\n[bold]Syncing with existing project:[/bold] {project_id}"
                )

                # Fetch existing project and milestones
                try:
                    project_data = client.get_project(project_id)
                    console.print(f"  Project: {project_data['name']}")

                    existing_milestones = client.get_project_milestones(project_id)
                    console.print(f"  Existing milestones: {len(existing_milestones)}")
                except WfpApiError as e:
                    console.print(f"\n[red]✗ Failed to fetch project:[/red] {e}")
                    if e.status_code == 404:
                        console.print(
                            "  Project not found. Use --mode=initial to create it."
                        )
                    sys.exit(2)

                # Validate milestone consistency
                console.print("\n[bold]Validating milestone consistency...[/bold]")
                try:
                    validate_for_sync_import(data, existing_milestones)
                    console.print("[green]✓[/green] Milestone validation passed")
                except ValidationError as e:
                    console.print("\n[red]✗ Validation failed:[/red]")
                    for error in e.errors:
                        console.print(f"  • {error.get('error', error)}")
                    console.print(
                        "\n[yellow]Tip:[/yellow] Milestone structure must not "
                        "change during sync."
                    )
                    console.print(
                        "  If milestones changed, consider creating a new project."
                    )
                    sys.exit(1)

                console.print("\n[bold]Syncing tasks...[/bold]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Syncing...", total=None)

                    import_summary = client.import_msproject_data(
                        project_id, data, mode="sync"
                    )

                    progress.update(task, completed=True)

                console.print("\n[green]✓[/green] Sync completed:")
                console.print(f"  Tasks created: {import_summary['tasks_created']}")
                console.print(f"  Tasks updated: {import_summary['tasks_updated']}")
                if data.assignments:
                    console.print(
                        "  Assignments created: "
                        f"{import_summary['assignments_created']}"
                    )
                else:
                    console.print("  Assignments created: 0 (none in XML)")

                if import_summary["tasks_failed"] > 0:
                    console.print(
                        f"  [yellow]⚠ Tasks failed: "
                        f"{import_summary['tasks_failed']}[/yellow]"
                    )

                if import_summary["failed_batches"]:
                    console.print(
                        f"\n[yellow]⚠ "
                        f"{len(import_summary['failed_batches'])} "
                        f"batch(es) failed[/yellow]"
                    )
                    for fb in import_summary["failed_batches"]:
                        console.print(
                            f"  • {fb['batch_type']} batch "
                            f"{fb.get('batch_num', 'N/A')}: {fb['error']}"
                        )

                # Create success report
                report = ImportReport(
                    correlation_id=correlation_id,
                    mode=ImportMode.SYNC,
                    success=True,
                    project_id=uuid.UUID(project_id),
                    created_count=import_summary["tasks_created"],
                    updated_count=import_summary["tasks_updated"],
                )

            if output_report:
                with open(output_report, "w") as f:
                    f.write(report.model_dump_json(indent=2))
                console.print(f"\n[green]✓[/green] Report saved to {output_report}")

        except WfpApiError as e:
            logger.error(f"API error: {e}")
            console.print(f"\n[red]✗ API error:[/red] {e}")
            if e.status_code == 403:
                console.print("  Permission denied. Check Guardian permissions.")
            elif e.status_code == 429:
                console.print("  Rate limit exceeded. Wait and try again.")
            sys.exit(2)

    except MSProjectParserError as e:
        logger.error(f"Parser error: {e}")
        console.print(f"\n[red]✗ Parsing failed:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        console.print(f"\n[red]✗ Unexpected error:[/red] {redact_secrets(str(e))}")
        sys.exit(3)
    finally:
        log_duration(start_time, "msproject command", logger)
