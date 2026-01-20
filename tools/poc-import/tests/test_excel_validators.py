# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for Excel validators."""

from datetime import date

from poc_import.models import ExpenseRow, RAEEntry, RAETaskBreakdown
from poc_import.validators import (
    ValidationSeverity,
    validate_expense_rows,
    validate_rae_entries,
)


def test_validate_expenses_requires_vendor_for_purchase():
    """Test vendor requirement for purchase expenses.

    Given: A purchase row without vendor name
    When: Validation is executed
    Then: VAL-EXP-006 is reported as an error
    """
    rows = [
        ExpenseRow(
            row_number=2,
            purchase_document="4500123456",
            fiscal_year=2025,
            period=1,
            otp_element="PROJ-001-INFRA",
            accounting_nature_label="Matériel informatique",
            reference_number="REF-2025-0042",
            amount=100.0,
            expense_date=date(2025, 1, 15),
        )
    ]

    report = validate_expense_rows(rows)

    assert report.has_errors() is True
    assert any(issue.id == "VAL-EXP-006" for issue in report.checks)


def test_validate_rae_breakdown_sum_mismatch():
    """Test task breakdown sum mismatch validation.

    Given: RAE entry with breakdown sum not matching remaining amount
    When: Validation is executed
    Then: VAL-RAE-004 is reported as an error
    """
    entry = RAEEntry(
        entry_id=1,
        milestone_name="Phase 1",
        remaining_amount=100.0,
        forecast_date=date(2026, 3, 31),
        task_breakdown=[RAETaskBreakdown(task_name="Task A", amount=50.0)],
        breakdown_sum=50.0,
        row_number=2,
    )

    report = validate_rae_entries([entry], milestone_names={"Phase 1"})

    assert report.has_errors() is True
    issue = next(issue for issue in report.checks if issue.id == "VAL-RAE-004")
    assert issue.severity == ValidationSeverity.ERROR
