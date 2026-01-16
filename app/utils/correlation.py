# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Correlation ID and error response utilities.

This module provides shared utilities for correlation ID tracking
and standardized error response formatting across all endpoints.
"""

import uuid
from typing import Any

from flask import g, request

# Typing helper for Flask-style responses (body, status[, headers])
ResponseTuple = tuple[Any, int] | tuple[Any, int, dict[str, str]]


def get_correlation_id() -> str:
    """Return current correlation ID or generate one.

    Checks Flask g context for existing correlation_id, then request headers,
    and generates a new UUID if neither exists.

    Returns:
        Correlation ID as string.
    """
    correlation_id = getattr(g, "correlation_id", None)
    if correlation_id:
        return str(correlation_id)

    header_value = request.headers.get("X-Correlation-ID")
    if header_value:
        g.correlation_id = header_value
        return header_value

    generated = str(uuid.uuid4())
    g.correlation_id = generated
    return generated


def error_response(
    message: str,
    status_code: int,
    *,
    error: str | None = None,
    errors: Any = None,
) -> ResponseTuple:
    """Build a spec-compliant error response with correlation header.

    Creates an error response following the OpenAPI Error schema format
    with correlation_id tracking and X-Correlation-ID response header.

    Args:
        message: Human-readable error message.
        status_code: HTTP status code for the error.
        error: Optional error type/category (e.g., "Bad Request").
        errors: Optional detailed validation errors dictionary.

    Returns:
        Tuple of (response body dict, status code, headers dict).
    """
    correlation_id = get_correlation_id()

    body: dict[str, Any] = {
        "message": message,
        "correlation_id": correlation_id,
    }
    if error:
        body["error"] = error
    if errors:
        body["errors"] = errors

    return body, status_code, {"X-Correlation-ID": correlation_id}
