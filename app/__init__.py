# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Flask application factory and initialization.

This module provides the application factory pattern for creating
Flask application instances with proper configuration and extension
initialization.
"""

import math
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional, cast

from flask import Flask, g, request

if TYPE_CHECKING:
    from flask import Response

from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import Gauge
from prometheus_flask_exporter import PrometheusMetrics

from app.utils.correlation import error_response

# Initialize extensions
db = SQLAlchemy(session_options={"expire_on_commit": False})
migrate = Migrate()
ma = Marshmallow()
limiter = Limiter(key_func=get_remote_address)
metrics: PrometheusMetrics | None = None  # Initialized in create_app

# Module-level cache for SQLAlchemy pool metrics Gauges
# Avoids accessing private REGISTRY._names_to_collectors
_pool_metrics_cache: dict[str, Gauge] = {}


def create_app(config_class: str = "app.config.DevelopmentConfig") -> Flask:
    """Create and configure Flask application instance.

    Factory function that creates a Flask application with proper
    configuration, extension initialization, and route registration.

    Args:
        config_class: Fully qualified class name for configuration.
                     Example: "app.config.DevelopmentConfig"

    Returns:
        Configured Flask application instance.

    Examples:
        >>> app = create_app("app.config.ProductionConfig")
        >>> app.run()
    """
    app = Flask(__name__)

    # Load configuration from class path
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    # Keep primary keys accessible after commits to avoid DetachedInstanceError in tests
    db.session.expire_on_commit = False  # type: ignore[attr-defined]
    migrate.init_app(app, db)
    ma.init_app(app)

    # Import models for migrations autogenerate
    with app.app_context():
        from app.models import Dummy  # noqa: F401

    # Configure rate limiting (initialize even when disabled so decorators are safe)
    limiter.enabled = app.config.get("RATE_LIMIT_ENABLED", True)
    limiter.init_app(app)

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e: RateLimitExceeded):
        """Return OpenAPI-compliant 429 with rate limit headers."""
        reset_at = getattr(e, "reset_at", None)
        headers: dict[str, str] = {}

        if reset_at:
            retry_after = max(0, math.ceil(reset_at - time.time()))
            headers["Retry-After"] = str(retry_after)
            headers["X-RateLimit-Reset"] = str(int(reset_at))

        response = error_response(
            "Rate limit exceeded. Maximum allowed by policy reached.",
            429,
            error="Too Many Requests",
        )
        body = response[0]
        status = response[1]
        # Merge rate limit headers with correlation headers from response
        if len(response) > 2:
            base_headers = response[2]
            base_headers.update(headers)
            return body, status, base_headers
        # Fallback if no headers dict in tuple
        return body, status, headers

    # Configure Prometheus metrics
    if app.config.get("PROMETHEUS_METRICS_ENABLED"):
        global metrics
        # Exclude health endpoints from metrics (AC-007, GUD-005)
        metrics = PrometheusMetrics(
            app,
            defaults_prefix="flask",
            excluded_paths=["/health", "/ready", "/version"],
        )
        # Don't register app_info gauge if already exists (for tests)
        with suppress(ValueError):
            metrics.info(
                "app_info",
                "Application info",
                version=app.config.get("SERVICE_VERSION", "1.0.0"),
            )

        # Instrument SQLAlchemy connection pool metrics (AC-006, REQ-005)
        # Use module-level cache to avoid private REGISTRY access
        global _pool_metrics_cache
        if not _pool_metrics_cache:
            try:
                _pool_metrics_cache["pool_size"] = Gauge(
                    "sqlalchemy_pool_size",
                    "Current size of the connection pool",
                    ["pool_name"],
                )
                _pool_metrics_cache["checked_in"] = Gauge(
                    "sqlalchemy_pool_checked_in_connections",
                    "Number of connections currently checked in to the pool",
                    ["pool_name"],
                )
                _pool_metrics_cache["checked_out"] = Gauge(
                    "sqlalchemy_pool_checked_out_connections",
                    "Number of connections currently checked out of the pool",
                    ["pool_name"],
                )
                _pool_metrics_cache["overflow"] = Gauge(
                    "sqlalchemy_pool_overflow",
                    "Number of connections in overflow",
                    ["pool_name"],
                )
            except ValueError:
                # Metrics already registered - should not happen with cache, but defensive
                pass

        @app.before_request
        def update_sqlalchemy_pool_metrics() -> None:
            """Update SQLAlchemy pool metrics only when /metrics is called.

            This reduces overhead on user-facing endpoints by only updating
            pool metrics when they are actually being scraped.
            """
            # Only update metrics when /metrics endpoint is called
            if request.path != "/metrics":
                return

            from sqlalchemy.pool import QueuePool

            if not _pool_metrics_cache or not hasattr(db.engine, "pool"):
                return

            pool = db.engine.pool
            pool_name = str(db.engine.url.database or "default")
            # Only QueuePool has size(), checkedin(), checkedout(), overflow()
            if isinstance(pool, QueuePool):
                _pool_metrics_cache["pool_size"].labels(pool_name=pool_name).set(
                    pool.size()
                )
                _pool_metrics_cache["checked_in"].labels(pool_name=pool_name).set(
                    pool.checkedin()
                )
                _pool_metrics_cache["checked_out"].labels(pool_name=pool_name).set(
                    pool.checkedout()
                )
                _pool_metrics_cache["overflow"].labels(pool_name=pool_name).set(
                    pool.overflow()
                )

        # Define authentication functions outside the request handler for efficiency
        from app.utils.metrics_auth import require_metrics_api_key

        # Rate limit function wrapped with limiter
        if app.config.get("RATE_LIMIT_ENABLED"):
            rate_limit_default = app.config.get("RATE_LIMIT_DEFAULT", "10 per minute")

            @limiter.limit(rate_limit_default)
            def _check_auth_with_rate_limit() -> "tuple[Response, int] | None":
                """Check authentication with rate limiting applied."""
                return require_metrics_api_key()

        else:

            def _check_auth_with_rate_limit() -> "tuple[Response, int] | None":
                """Check authentication without rate limiting."""
                return require_metrics_api_key()

        @app.before_request
        def authenticate_metrics() -> "tuple[Response, int] | None":
            """Authenticate /metrics endpoint requests.

            Validates API key via Authorization header before allowing
            access to Prometheus metrics endpoint.

            Returns:
                Error response tuple if authentication fails, None otherwise.
            """
            if request.path == "/metrics":
                # Check authentication (and rate limit if enabled)
                return _check_auth_with_rate_limit()
            return None

    # Configure CORS
    if app.config.get("CORS_ORIGINS"):
        CORS(
            app,
            origins=app.config["CORS_ORIGINS"],
            supports_credentials=app.config.get("CORS_ALLOW_CREDENTIALS", True),
        )

    # Register routes
    with app.app_context():
        from app.routes import register_routes

        register_routes(app)

    # Add security headers
    if app.config.get("SECURITY_HEADERS_ENABLED"):

        @app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            for header, value in app.config["SECURITY_HEADERS"].items():
                response.headers[header] = value
            return response

    # Configure logging
    from app.utils.logger import setup_logging

    setup_logging(app)

    # Register CLI commands
    from app.cli import config

    app.cli.add_command(config)

    return app
