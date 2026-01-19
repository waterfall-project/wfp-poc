# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shared CLI helpers and console setup."""

import logging
import os
import re

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def redact_secrets(message: str) -> str:
    """Redact secrets from log or error messages.

    Args:
        message: Message that may include secrets.

    Returns:
        Redacted message safe for display.
    """
    redacted = message
    secret_keys = [
        "WFP_JWT_TOKEN",
        "JWT_SECRET_KEY",
        "WFP_USER_ID",
        "WFP_COMPANY_ID",
    ]
    for key in secret_keys:
        value = os.getenv(key)
        if value:
            redacted = redacted.replace(value, "***")

    jwt_pattern = re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
    redacted = jwt_pattern.sub("***", redacted)
    return redacted


def setup_logging(verbose: bool) -> None:
    """Setup logging configuration for CLI commands."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )
