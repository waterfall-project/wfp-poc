# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for CLI commands."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from poc_import.cli import cli


class TestCLI:
    """Test cases for CLI commands."""

    def test_cli_version(self):
        """Test version command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_help(self):
        """Test help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "poc-import" in result.output
        assert "msproject" in result.output
        assert "excel" in result.output

    def test_msproject_help(self):
        """Test msproject subcommand help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["msproject", "--help"])
        assert result.exit_code == 0
        assert "Import MS Project XML file" in result.output
        assert "--mode" in result.output
        assert "--dry-run" in result.output

    def test_msproject_missing_mode(self, sample_msproject_xml):
        """Test msproject without --mode argument."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(sample_msproject_xml)
            tmp_path = tmp.name

        try:
            result = runner.invoke(cli, ["msproject", tmp_path])
            assert result.exit_code != 0
            assert "mode" in result.output.lower()
        finally:
            Path(tmp_path).unlink()

    def test_msproject_dry_run(self, sample_msproject_xml):
        """Test msproject with dry-run mode."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(sample_msproject_xml)
            tmp_path = tmp.name

        try:
            result = runner.invoke(
                cli,
                [
                    "msproject",
                    tmp_path,
                    "--mode=initial",
                    "--token=dummy-token",
                    "--dry-run",
                ],
            )
            assert result.exit_code == 0
            assert "Dry run mode" in result.output
            assert "Validation passed" in result.output
        finally:
            Path(tmp_path).unlink()

    def test_msproject_sync_without_project_id(self, sample_msproject_xml):
        """Test sync mode without project ID."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(sample_msproject_xml)
            tmp_path = tmp.name

        try:
            result = runner.invoke(
                cli,
                [
                    "msproject",
                    tmp_path,
                    "--mode=sync",
                    "--token=dummy-token",
                ],
            )
            assert result.exit_code == 1
            assert "project-id is required" in result.output
        finally:
            Path(tmp_path).unlink()

    def test_expenses_not_implemented(self):
        """Test expenses command (not yet implemented)."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = runner.invoke(
                cli,
                [
                    "excel",
                    "expenses",
                    tmp_path,
                    "--project-id=12345678-1234-1234-1234-123456789012",
                    "--token=dummy-token",
                ],
            )
            assert result.exit_code == 0
            assert "not yet implemented" in result.output
        finally:
            Path(tmp_path).unlink()

    def test_rae_not_implemented(self):
        """Test RAE command (not yet implemented)."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = runner.invoke(
                cli,
                [
                    "excel",
                    "rae",
                    tmp_path,
                    "--project-id=12345678-1234-1234-1234-123456789012",
                    "--token=dummy-token",
                ],
            )
            assert result.exit_code == 0
            assert "not yet implemented" in result.output
        finally:
            Path(tmp_path).unlink()

    def test_msproject_missing_token_error(
        self, sample_msproject_xml, monkeypatch, tmp_path
    ):
        """Test msproject error when token is missing.

        Given: No JWT token is available in env
        When: msproject runs without --token
        Then: A clear error is shown
        """
        runner = CliRunner()
        monkeypatch.delenv("WFP_JWT_TOKEN", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("WFP_USER_ID", raising=False)
        monkeypatch.delenv("WFP_COMPANY_ID", raising=False)
        monkeypatch.setenv("WFP_ENV_FILE", str(tmp_path / "missing.env"))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as tmp:
            tmp.write(sample_msproject_xml)
            xml_file_path = tmp.name

        try:
            result = runner.invoke(
                cli,
                [
                    "msproject",
                    xml_file_path,
                    "--mode=initial",
                ],
            )
            assert result.exit_code == 1
            assert "--token is required" in result.output
        finally:
            Path(xml_file_path).unlink()
