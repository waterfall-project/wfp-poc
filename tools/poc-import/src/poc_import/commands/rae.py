# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Excel RAE import command."""

import logging
import sys
import time
import uuid
from pathlib import Path

import click

from poc_import.cli_support import (
    console,
    log_duration,
    set_correlation_id,
    setup_logging,
)
from poc_import.config import Config, load_env_file


@click.command(help="Import RAE from an Excel file (not implemented).")
@click.argument("excel_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--project-id",
    type=str,
    required=True,
    help="Project UUID",
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
def rae(
    excel_file: Path,
    project_id: str,
    env_name: str | None,
    token: str | None,
    api_url: str,
    dry_run: bool,
    log_level: str | None,
    verbose: bool,
) -> None:
    """Import RAE (Reste À Engager) from Excel file."""
    setup_logging(verbose, log_level)
    load_env_file(env_name)
    logger = logging.getLogger(__name__)
    start_time = time.monotonic()
    set_correlation_id(str(uuid.uuid4()))
    config = Config()

    api_url = api_url or config.api_url
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

    console.print("[yellow]⚠ Excel RAE import not yet implemented[/yellow]")
    console.print(f"  File: {excel_file}")
    console.print(f"  Project ID: {project_id}")
    log_duration(start_time, "excel rae", logger)
    sys.exit(0)
