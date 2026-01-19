# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shared CLI helpers and console setup."""

import contextvars
import logging
import os
import re
import time

from rich.console import Console
from rich.logging import RichHandler

console = Console()

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)
_base_log_record_factory = logging.getLogRecordFactory()


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


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for the current command context."""
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get correlation ID for the current command context."""
    return _correlation_id_var.get()


class CorrelationIdFilter(logging.Filter):
    """Attach correlation ID and redact secrets in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        message = record.getMessage()
        redacted = redact_secrets(message)
        record.msg = redacted
        record.args = ()
        return True


def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _base_log_record_factory(*args, **kwargs)
    if not hasattr(record, "correlation_id"):
        record.correlation_id = get_correlation_id()
    return record


def log_duration(start_time: float, label: str, logger: logging.Logger) -> None:
    """Log duration if operation exceeds 1 second.

    Args:
        start_time: Start timestamp from time.monotonic().
        label: Operation label to log.
        logger: Logger instance.
    """
    duration = time.monotonic() - start_time
    if duration >= 1.0:
        logger.info("Completed %s in %.2fs", label, duration)


def setup_logging(verbose: bool, log_level: str | None = None) -> None:
    """Setup logging configuration for CLI commands."""
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    if log_level:
        level = level_map.get(log_level.lower(), logging.INFO)
    else:
        level = logging.DEBUG if verbose else logging.INFO
    logging.setLogRecordFactory(_record_factory)
    logging.basicConfig(
        level=level,
        format="%(message)s [correlation_id=%(correlation_id)s]",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
        force=True,
    )
    logging.getLogger().addFilter(CorrelationIdFilter())
