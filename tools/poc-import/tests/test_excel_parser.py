# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for Excel parsers."""

from datetime import date

from openpyxl import Workbook

from poc_import.parsers.excel import parse_expenses_excel, parse_rae_excel


def test_parse_expenses_groups_by_reference(tmp_path):
    """Test grouping by reference number.

    Given: Two expense rows with the same reference number
    When: The expenses Excel file is parsed
    Then: A single grouped entry is returned with summed amount
    """
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
            "Dell",
            "6100",
            "Matériel informatique",
            "REF-2025-0042",
            100.00,
            date(2025, 1, 15),
            "Server",
            "GRP-ADMIN",
            "PO-2025-0023",
        ]
    )
    sheet.append(
        [
            "4500123456",
            2025,
            1,
            "PROJ-001-INFRA",
            "",
            "Dell",
            "6100",
            "Matériel informatique",
            "REF-2025-0042",
            200.00,
            date(2025, 1, 15),
            "Server",
            "GRP-ADMIN",
            "PO-2025-0023",
        ]
    )
    excel_path = tmp_path / "expenses.xlsx"
    workbook.save(excel_path)

    data = parse_expenses_excel(excel_path)

    assert data.total_rows == 2
    assert len(data.entries) == 1
    assert data.entries[0].amount == 300.00
    assert data.entries[0].grouped_rows == 2


def test_parse_rae_with_breakdown(tmp_path):
    """Test parsing RAE entries with task breakdown.

    Given: A RAE Excel file with JSON task breakdown
    When: The RAE Excel file is parsed
    Then: The breakdown is parsed and summed
    """
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
            '[{"task_name": "Infra", "amount": 50000}]',
        ]
    )
    excel_path = tmp_path / "rae.xlsx"
    workbook.save(excel_path)

    data = parse_rae_excel(excel_path)

    assert data.total_rows == 1
    assert data.entries[0].breakdown_sum == 50000
    assert len(data.entries[0].task_breakdown) == 1
