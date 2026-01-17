# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""JWT authentication and RBAC authorization decorators.

This module provides decorators for JWT-based authentication and
Guardian-based authorization, extracting user claims and checking permissions.
"""

import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

import jwt
from flask import current_app, g, request
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidTokenError

from app.services.guardian_service import GuardianError, GuardianService, Operation
from app.utils.correlation import error_response as _error_response

# Typing helper for Flask-style responses (body, status[, headers])
ResponseTuple = tuple[Any, int] | tuple[Any, int, dict[str, str]]


class JWTError(Exception):
    """Base exception for JWT-related errors.

    Attributes:
        message: Error description.
        status_code: HTTP status code for the error.
    """

    def __init__(self, message: str, status_code: int = 401) -> None:
        """Initialize JWT error.

        Args:
            message: Error description.
            status_code: HTTP status code (default: 401 Unauthorized).
        """
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _get_correlation_id() -> str:
    return str(getattr(g, "correlation_id", "N/A"))


def _extract_token() -> str | None:
    token = request.cookies.get(current_app.config["JWT_COOKIE_NAME"])
    if token:
        return token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip() or None

    return None


def _decode_token(token: str) -> dict[str, Any] | ResponseTuple:
    try:
        decoded: Any = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
        if not isinstance(decoded, dict):
            current_app.logger.error(
                "JWT payload is not an object",
                extra={"correlation_id": _get_correlation_id()},
            )
            return _error_response("Invalid token.", 401, error="Unauthorized")
        return decoded
    except ExpiredSignatureError:
        current_app.logger.warning(
            "JWT token expired",
            extra={"correlation_id": _get_correlation_id()},
        )
        return _error_response("Token has expired.", 401, error="Unauthorized")
    except DecodeError:
        current_app.logger.error(
            "JWT decode error",
            extra={"correlation_id": _get_correlation_id()},
        )
        return _error_response("Invalid token format.", 401, error="Unauthorized")
    except InvalidTokenError as exc:
        current_app.logger.error(
            "JWT validation error",
            extra={
                "correlation_id": _get_correlation_id(),
                "error": str(exc),
            },
        )
        return _error_response("Invalid token.", 401, error="Unauthorized")


def _validate_string_claim(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value


def _set_user_context(payload: dict[str, Any]) -> bool:
    user_id = _validate_string_claim(payload.get("user_id"))
    company_id = _validate_string_claim(payload.get("company_id"))

    g.user_id = user_id
    g.company_id = company_id
    g.email = payload.get("email") if isinstance(payload.get("email"), str) else None

    return bool(user_id and company_id)


def require_jwt_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to require JWT authentication.

    Validates JWT token from access_token cookie, decodes it, and places
    user claims (user_id, company_id, email) in Flask g context.

    The decorator expects the following claims in the JWT:
    - user_id: Unique identifier of the user
    - company_id: Unique identifier of the user's company
    - email: User's email address

    Args:
        f: Function to decorate.

    Returns:
        Decorated function with JWT authentication.

    Raises:
        JWTError: If token is missing, invalid, or expired.

    Examples:
        >>> @require_jwt_auth
        ... def protected_route():
        ...     user_id = g.user_id
        ...     return jsonify({"user_id": user_id})
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        """Wrapper function that validates JWT before calling original.

        Args:
            *args: Positional arguments for wrapped function.
            **kwargs: Keyword arguments for wrapped function.

        Returns:
            Response from wrapped function or error response.
        """
        token = _extract_token()
        if not token:
            current_app.logger.warning(
                "Missing JWT token",
                extra={"correlation_id": _get_correlation_id()},
            )
            return _error_response(
                "Authentication required. No token provided.",
                401,
                error="Unauthorized",
            )

        decoded = _decode_token(token)
        if not isinstance(decoded, dict):
            return decoded

        if not _set_user_context(decoded):
            current_app.logger.error(
                "JWT token missing required claims",
                extra={
                    "correlation_id": _get_correlation_id(),
                    "has_user_id": bool(getattr(g, "user_id", None)),
                    "has_company_id": bool(getattr(g, "company_id", None)),
                },
            )
            return _error_response(
                "Invalid token: missing required claims.",
                401,
                error="Unauthorized",
            )

        current_app.logger.debug(
            "JWT authentication successful",
            extra={
                "correlation_id": _get_correlation_id(),
                "user_id": g.user_id,
                "company_id": g.company_id,
            },
        )

        return f(*args, **kwargs)

    return decorated_function


def get_current_user_id() -> str | None:
    """Get the current authenticated user ID from context.

    Returns:
        User ID from JWT claims or None if not authenticated.

    Examples:
        >>> @require_jwt_auth
        ... def my_route():
        ...     user_id = get_current_user_id()
        ...     return jsonify({"user_id": user_id})
    """
    return getattr(g, "user_id", None)


def get_current_company_id() -> str | None:
    """Get the current authenticated user's company ID from context.

    Returns:
        Company ID from JWT claims or None if not authenticated.

    Examples:
        >>> @require_jwt_auth
        ... def my_route():
        ...     company_id = get_current_company_id()
        ...     return jsonify({"company_id": company_id})
    """
    return getattr(g, "company_id", None)


def get_current_company_uuid() -> uuid.UUID | None:
    """Get the current authenticated user's company ID as UUID.

    Returns:
        Company UUID parsed from JWT claims or None if unavailable/invalid.
    """
    company_id = get_current_company_id()
    if not company_id:
        return None
    try:
        return uuid.UUID(company_id)
    except ValueError:
        return None


def _infer_resource_name(explicit_name: str | None) -> str | None:
    if explicit_name:
        return explicit_name

    endpoint = request.endpoint
    if not endpoint:
        return None

    parts = endpoint.split(".")
    if len(parts) <= 1:
        return None

    return parts[-1].replace("_resource", "s")


def _get_user_context_or_error() -> tuple[tuple[str, str] | None, ResponseTuple | None]:
    user_id = get_current_user_id()
    company_id = get_current_company_id()
    if user_id and company_id:
        return (user_id, company_id), None

    current_app.logger.error(
        "Missing user context for authorization",
        extra={
            "correlation_id": _get_correlation_id(),
        },
    )
    return (
        None,
        _error_response(
            "User context missing. Use @require_jwt_auth first.",
            401,
            error="Unauthorized",
        ),
    )


def _build_guardian_context(kwargs: dict[str, Any]) -> dict[str, str] | None:
    context = {key: str(value) for key, value in kwargs.items() if key != "version"}
    return context or None


def _check_guardian_access_or_error(
    *,
    user_id: str,
    company_id: str,
    resource_name: str,
    operation: Operation,
    context: dict[str, str] | None,
) -> ResponseTuple | None:
    try:
        access_granted, reason = GuardianService.check_access(
            user_id=user_id,
            company_id=company_id,
            resource_name=resource_name,
            operation=operation,
            context=context,
        )

        if access_granted:
            return None

        current_app.logger.warning(
            "Access denied by Guardian",
            extra={
                "user_id": user_id,
                "company_id": company_id,
                "resource_name": resource_name,
                "operation": operation.value,
                "reason": reason,
                "correlation_id": _get_correlation_id(),
            },
        )
        return _error_response(f"Access denied: {reason}", 403, error="Forbidden")

    except GuardianError as exc:
        current_app.logger.error(
            "Guardian service error",
            extra={
                "error": str(exc),
                "correlation_id": _get_correlation_id(),
            },
        )
        return _error_response(
            "Authorization service unavailable.",
            503,
            error="Service Unavailable",
        )


def get_current_user_email() -> str | None:
    """Get the current authenticated user's email from context.

    Returns:
        Email from JWT claims or None if not authenticated.

    Examples:
        >>> @require_jwt_auth
        ... def my_route():
        ...     email = get_current_user_email()
        ...     return jsonify({"email": email})
    """
    return getattr(g, "email", None)


def access_required(
    operation: Operation, resource_name: str | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to require Guardian RBAC authorization.

    Checks if the authenticated user has permission to perform
    the specified operation on the resource. Must be used after
    @require_jwt_auth as it depends on user_id and company_id in context.

    Args:
        operation: RBAC operation (LIST, CREATE, READ, UPDATE, DELETE).
        resource_name: Name of the resource (default: extracted from route).

    Returns:
        Decorator function that enforces authorization.

    Raises:
        GuardianError: If Guardian service is unavailable.

    Examples:
        >>> @require_jwt_auth
        ... @access_required(Operation.READ, "projects")
        ... def get_project(project_id):
        ...     return jsonify({"id": project_id})
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            """Wrapper that checks Guardian permissions before calling original.

            Args:
                *args: Positional arguments for wrapped function.
                **kwargs: Keyword arguments for wrapped function.

            Returns:
                Response from wrapped function or 403 error.
            """
            nonlocal resource_name
            resource_name = _infer_resource_name(resource_name)
            if not resource_name:
                current_app.logger.error(
                    "Cannot determine resource name for access check",
                    extra={
                        "endpoint": request.endpoint,
                        "correlation_id": _get_correlation_id(),
                    },
                )
                return _error_response(
                    "Cannot determine resource for authorization.",
                    500,
                    error="Internal Server Error",
                )

            user_ctx, user_err = _get_user_context_or_error()
            if user_err:
                return user_err

            assert user_ctx is not None
            user_id, company_id = user_ctx
            context = _build_guardian_context(kwargs)

            guardian_err = _check_guardian_access_or_error(
                user_id=user_id,
                company_id=company_id,
                resource_name=resource_name,
                operation=operation,
                context=context,
            )
            if guardian_err:
                return guardian_err

            return f(*args, **kwargs)

        return decorated_function

    return decorator
