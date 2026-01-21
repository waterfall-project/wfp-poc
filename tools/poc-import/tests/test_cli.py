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

    def test_xml_import_help_includes_create_project(self):
        """Test xml import help lists create-project."""
        runner = CliRunner()
        result = runner.invoke(cli, ["xml", "import", "--help"])
        assert result.exit_code == 0
        assert "create-project" in result.output

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

    def test_excel_load_expenses(self, tmp_path):
        """Test excel load for expenses.

        Given: A valid expenses Excel file
        When: excel load is executed with type expenses
        Then: Output confirms Excel file is loaded
        """
        from datetime import date

        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Dépenses"
        sheet.append(
            [
                "Document d'achat",
                "Exercice comptable",
                "Période",
                "Elément d'OTP",
                "Nom Matricule",
                "Nom 1",
                "Nature comptable",
                "Désign.nat.comptable",
                "Nº pièce référence",
                "Val./Devise objet",
                "Date de la pièce",
                "Texte de la commande d'achat",
                "Groupe d'origine",
                "Référence",
            ]
        )
        sheet.append(
            [
                "4500123456",
                2025,
                1,
                "PROJ-001-INFRA",
                "",
                "Dell Technologies France",
                "6100",
                "Matériel informatique",
                "REF-2025-0042",
                12500.00,
                date(2025, 1, 15),
                "Serveurs Dell PowerEdge R750 (x2)",
                "GRP-ADMIN",
                "PO-2025-0023",
            ]
        )
        excel_path = tmp_path / "expenses.xlsx"
        workbook.save(excel_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["excel", "load", str(excel_path), "--type", "expenses"],
        )

        assert result.exit_code == 0
        assert "Excel loaded" in result.output
        assert "Type: Expenses" in result.output

    def test_excel_load_rae(self, tmp_path):
        """Test excel load for RAE.

        Given: A valid RAE Excel file
        When: excel load is executed with type rae
        Then: Output confirms Excel file is loaded
        """
        from datetime import date

        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "RAE Forecast"
        sheet.append(
            [
                "milestone_name",
                "remaining_amount",
                "forecast_date",
                "task_breakdown",
            ]
        )
        sheet.append(
            [
                "Phase 1: Foundation",
                125000.00,
                date(2026, 3, 31),
                "[]",
            ]
        )
        excel_path = tmp_path / "rae.xlsx"
        workbook.save(excel_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["excel", "load", str(excel_path), "--type", "rae"],
        )

        assert result.exit_code == 0
        assert "Excel loaded" in result.output
        assert "Type: RAE" in result.output

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
