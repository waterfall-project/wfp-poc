# Copyright (c) 2025 Waterfall
#
# This source code is dual-licensed under:
# - GNU Affero General Public License v3.0 (AGPLv3) for open source use
# - Commercial License for proprietary use
#
# See LICENSE and LICENSE.md files in the root directory for full license text.
# For commercial licensing inquiries, contact: contact@waterfall-project.pro

"""Unit tests for correlation utility functions."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from app.utils.correlation import error_response, get_correlation_id


class TestGetCorrelationId:
    """Tests for get_correlation_id function."""

    def test_get_correlation_id_from_g_context(self, app: Flask) -> None:
        """Get correlation ID from Flask g context.

        Given: correlation_id is set in Flask g
        When: get_correlation_id() is called
        Then: Returns the correlation_id from g
        """
        with app.test_request_context():
            expected_id = str(uuid.uuid4())
            g.correlation_id = expected_id

            result = get_correlation_id()

            assert result == expected_id

    def test_get_correlation_id_from_request_header(self, app: Flask) -> None:
        """Get correlation ID from request header.

        Given: X-Correlation-ID header is present
        When: get_correlation_id() is called
        Then: Returns the correlation_id from header and sets g
        """
        with app.test_request_context(headers={"X-Correlation-ID": "test-id-123"}):
            # Ensure g is clean for this test
            if hasattr(g, "correlation_id"):
                delattr(g, "correlation_id")

            result = get_correlation_id()

            assert result == "test-id-123"
            assert g.correlation_id == "test-id-123"

    def test_get_correlation_id_generates_new(self, app: Flask) -> None:
        """Generate new correlation ID when none exists.

        Given: No correlation_id in g or header
        When: get_correlation_id() is called
        Then: Generates new UUID and sets g
        """
        with app.test_request_context():
            # Ensure g is clean for this test
            if hasattr(g, "correlation_id"):
                delattr(g, "correlation_id")

            result = get_correlation_id()

            # Verify it's a valid UUID
            assert uuid.UUID(result)
            assert g.correlation_id == result

    def test_get_correlation_id_header_priority(self, app: Flask) -> None:
        """Request header takes priority over generation.

        Given: X-Correlation-ID header is present
        When: get_correlation_id() is called multiple times
        Then: Returns same ID from header on first call
        """
        with app.test_request_context(headers={"X-Correlation-ID": "header-id"}):
            # Ensure g is clean for this test
            if hasattr(g, "correlation_id"):
                delattr(g, "correlation_id")

            first_call = get_correlation_id()
            second_call = get_correlation_id()

            assert first_call == "header-id"
            assert second_call == "header-id"


class TestErrorResponse:
    """Tests for error_response function."""

    def test_error_response_basic(self, app: Flask) -> None:
        """Create basic error response.

        Given: Error message and status code
        When: error_response() is called
        Then: Returns tuple with body, status, and headers
        """
        with app.test_request_context():
            body, status, headers = error_response("Test error", 400)

            assert status == 400
            assert body["message"] == "Test error"
            assert "correlation_id" in body
            assert "X-Correlation-ID" in headers
            assert headers["X-Correlation-ID"] == body["correlation_id"]

    def test_error_response_with_error_type(self, app: Flask) -> None:
        """Create error response with error type.

        Given: Error message, status code, and error type
        When: error_response() is called with error parameter
        Then: Includes error field in body
        """
        with app.test_request_context():
            body, status, headers = error_response(
                "Validation failed", 400, error="Bad Request"
            )

            assert status == 400
            assert body["message"] == "Validation failed"
            assert body["error"] == "Bad Request"
            assert "correlation_id" in body

    def test_error_response_with_errors_dict(self, app: Flask) -> None:
        """Create error response with validation errors.

        Given: Error message with validation errors dict
        When: error_response() is called with errors parameter
        Then: Includes errors field in body
        """
        with app.test_request_context():
            validation_errors = {"field1": ["Required"], "field2": ["Invalid"]}
            body, status, headers = error_response(
                "Validation failed", 400, errors=validation_errors
            )

            assert status == 400
            assert body["message"] == "Validation failed"
            assert body["errors"] == validation_errors
            assert "correlation_id" in body

    def test_error_response_preserves_provided_correlation_id(
        self, app: Flask
    ) -> None:
        """Preserve correlation ID from request header.

        Given: Request with X-Correlation-ID header
        When: error_response() is called
        Then: Uses same correlation_id in response
        """
        provided_id = str(uuid.uuid4())
        with app.test_request_context(headers={"X-Correlation-ID": provided_id}):
            # Ensure g is clean for this test
            if hasattr(g, "correlation_id"):
                delattr(g, "correlation_id")

            body, status, headers = error_response("Error", 500)

            assert body["correlation_id"] == provided_id
            assert headers["X-Correlation-ID"] == provided_id

    def test_error_response_all_parameters(self, app: Flask) -> None:
        """Create error response with all parameters.

        Given: All error response parameters
        When: error_response() is called with all params
        Then: Returns complete error response
        """
        with app.test_request_context():
            errors_dict = {"name": ["Required field"]}
            body, status, headers = error_response(
                "Validation failed",
                400,
                error="Bad Request",
                errors=errors_dict,
            )

            assert status == 400
            assert body["message"] == "Validation failed"
            assert body["error"] == "Bad Request"
            assert body["errors"] == errors_dict
            assert "correlation_id" in body
            assert uuid.UUID(body["correlation_id"])
            assert headers["X-Correlation-ID"] == body["correlation_id"]
