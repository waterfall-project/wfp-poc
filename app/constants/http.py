# Copyright (c) 2026 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Shared HTTP error types and common API messages.

Centralizes strings that were previously duplicated across resources.
Keep this small and generic (resource-specific messages should stay local).
"""

# Common OpenAPI-ish error type strings
BAD_REQUEST_ERROR = "Bad Request"
UNAUTHORIZED_ERROR = "Unauthorized"
FORBIDDEN_ERROR = "Forbidden"
NOT_FOUND_ERROR = "Not Found"
CONFLICT_ERROR = "Conflict"
UNPROCESSABLE_ENTITY_ERROR = "Unprocessable Entity"
INTERNAL_SERVER_ERROR = "Internal Server Error"
SERVICE_UNAVAILABLE_ERROR = "Service Unavailable"

# Common error messages
DEFAULT_UNSUPPORTED_API_VERSION_MSG = "Unsupported API version"
INVALID_PAGINATION_MSG = "Invalid pagination parameters"
INVALID_JSON_BODY_MSG = "Request body must be a JSON object"
VALIDATION_FAILED_MSG = "Validation failed"
INVALID_REQUEST_MSG = "Invalid request"

# Common invalid identifier messages
INVALID_PROJECT_ID_MSG = "Invalid project_id"
INVALID_UUID_MSG = "Invalid UUID format"
INVALID_TASK_ID_MSG = "Invalid task_id"
INVALID_RESOURCE_ID_MSG = "Invalid resource_id"
INVALID_ASSIGNMENT_ID_MSG = "Invalid assignment id"

# Common validation messages
MISSING_PROJECT_ID_MSG = "Missing project id"
MISSING_RESOURCE_ID_MSG = "Missing resource id"
AT_LEAST_ONE_FIELD_REQUIRED_MSG = "At least one field must be provided for update"
