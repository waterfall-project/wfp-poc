# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shared CLI helpers and console setup."""

import logging

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(verbose: bool) -> None:
    """Setup logging configuration for CLI commands."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )
