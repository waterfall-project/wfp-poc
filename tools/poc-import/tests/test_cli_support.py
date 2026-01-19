# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for CLI support helpers."""

from __future__ import annotations

from poc_import.cli_support import redact_secrets


def test_redact_secrets_env_values(monkeypatch):
    """Test redacting environment secret values.

    Given: Secret values in environment variables
    When: redact_secrets() is called
    Then: Secrets are masked in the output
    """
    monkeypatch.setenv("WFP_JWT_TOKEN", "env-token")
    message = "token=env-token"

    result = redact_secrets(message)

    assert "env-token" not in result
    assert "***" in result


def test_redact_secrets_jwt_pattern():
    """Test redacting JWT-like strings.

    Given: A JWT-like token in the message
    When: redact_secrets() is called
    Then: The token is masked
    """
    message = "auth=eyJabc.def123.ghi456"

    result = redact_secrets(message)

    assert "eyJabc.def123.ghi456" not in result
    assert "***" in result
