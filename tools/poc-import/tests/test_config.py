# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for configuration loading."""

from __future__ import annotations

import os

from poc_import.config import load_env_file


def test_load_env_file_dev(tmp_path, monkeypatch):
    """Test loading environment-specific .env file.

    Given: A .env.dev file in the current working directory
    When: load_env_file("dev") is called
    Then: The environment variables are loaded
    """
    env_file = tmp_path / ".env.dev"
    env_file.write_text("WFP_JWT_TOKEN=from_env\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WFP_JWT_TOKEN", raising=False)

    load_env_file("dev")

    assert os.getenv("WFP_JWT_TOKEN") == "from_env"
