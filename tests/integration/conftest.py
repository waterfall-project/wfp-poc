# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Pytest fixtures for integration tests.

This module provides common fixtures for integration testing with real
database connections and full application stack.
"""

import os
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app, db


@pytest.fixture(scope="session")
def app() -> Generator[Flask, None, None]:
    """Create Flask application instance for integration testing.

    Application is created once per test session for efficiency.
    Uses IntegrationConfig with real PostgreSQL database or SQLite.

    Yields:
        Flask application configured for integration tests.
    """
    os.environ["TESTING"] = "true"
    # Set METRICS_API_KEY for tests (required by config)
    os.environ["METRICS_API_KEY"] = "test-metrics-api-key-integration-12345678"

    # Ensure instance directory exists for SQLite
    instance_dir = Path(__file__).parent.parent.parent / "instance" / "data"
    instance_dir.mkdir(parents=True, exist_ok=True)

    app = create_app("app.config.IntegrationConfig")

    with app.app_context():
        # Create all tables
        db.create_all()
        yield app
        # Cleanup
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def client(app: Flask) -> FlaskClient:
    """Create Flask test client for making HTTP requests.

    Recreated for each test function to ensure isolation.

    Args:
        app: Flask application fixture.

    Returns:
        Flask test client for making HTTP requests.
    """
    return app.test_client()


@pytest.fixture
def generate_uuid() -> Callable[[], str]:
    """Generate UUID strings for test data."""

    def _generate() -> str:
        return str(uuid.uuid4())

    return _generate


@pytest.fixture
def company_id(generate_uuid: Callable[[], str]) -> str:
    """Provide a unique company ID for integration tests."""

    return generate_uuid()


@pytest.fixture
def user_claims(company_id: str, generate_uuid: Callable[[], str]) -> dict[str, Any]:
    """Standard JWT claims for integration tests."""

    return {
        "user_id": generate_uuid(),
        "company_id": company_id,
        "email": "integration@example.com",
        "roles": ["user"],
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }


@pytest.fixture
def generate_jwt(app: Flask) -> Callable[[dict[str, Any]], str]:
    """Factory to generate JWT tokens with the app secret."""

    jwt_secret = app.config["JWT_SECRET_KEY"]

    def _generate(claims: dict[str, Any]) -> str:
        token = jwt.encode(claims, jwt_secret, algorithm="HS256")
        return token.decode("utf-8") if isinstance(token, bytes) else token

    return _generate


@pytest.fixture
def integration_client(
    client: FlaskClient,
    user_claims: dict[str, Any],
    generate_jwt: Callable[[dict[str, Any]], str],
) -> FlaskClient:
    """Authenticated client with access_token cookie set."""

    token = generate_jwt(user_claims)
    client.set_cookie("access_token", token)
    return client


@pytest.fixture(autouse=True)
def mock_guardian_access() -> Generator[None, None, None]:
    """Stub Guardian access checks to always grant during integration tests."""

    with patch("app.utils.jwt_decorators.GuardianService.check_access") as mock:
        mock.return_value = (True, "granted")
        yield
