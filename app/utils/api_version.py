# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""API version helpers.

This service historically exposed versioned routes under `/v0/...`.
The OpenAPI spec defines versioned paths as `/{version}/...`.

To support both without duplicating logic, resources accept an optional
`version` path parameter and validate it with the helpers in this module.
"""

from __future__ import annotations

from app.constants.http import DEFAULT_UNSUPPORTED_API_VERSION_MSG
from app.utils.correlation import ResponseTuple, error_response

SUPPORTED_API_VERSIONS: set[str] = {"v0", "v1"}

UNSUPPORTED_VERSION_MSG = (
    "Unsupported API version: {version}. Supported versions: v0, v1."
)


def validate_api_version(version: str | None) -> tuple[dict[str, str], int] | None:
    """Validate an optional API version path parameter.

    Args:
        version: Version string from URL path, e.g. "v0".

    Returns:
        None if version is absent or supported, otherwise an error response tuple.
    """
    if version is None:
        return None

    if version not in SUPPORTED_API_VERSIONS:
        return (
            {
                "error": "Not Found",
                "message": UNSUPPORTED_VERSION_MSG.format(version=version),
            },
            404,
        )

    return None


def validate_api_version_or_error_response(version: str | None) -> ResponseTuple | None:
    """Validate API version and return a standardized error response when invalid.

    This removes duplicated boilerplate in resources.
    """
    version_error = validate_api_version(version)
    if not version_error:
        return None

    body, status_code = version_error
    return error_response(
        body.get("message", DEFAULT_UNSUPPORTED_API_VERSION_MSG),
        status_code,
        error=body.get("error"),
    )
