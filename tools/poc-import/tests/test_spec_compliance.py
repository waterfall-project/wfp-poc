# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Tests for spec compliance fixes (issues 81-83 production readiness)."""

from datetime import date

from poc_import.models import RAEEntry
from poc_import.validators import ValidationSeverity, validate_rae_entries


class TestRAETaskExistenceValidation:
    """Tests for VAL-RAE-005 blocking RAE import (spec REQ-059, REQ-060)."""

    def test_validation_error_when_task_not_in_xml(self) -> None:
        """Given task breakdown with missing tasks, validation returns ERROR."""
        entry = RAEEntry(
            entry_id=1,
            milestone_name="Phase 1",
            remaining_amount=100000.0,
            forecast_date=date(2026, 3, 31),
            task_breakdown=[
                {"task_name": "Existing Task", "amount": 50000.0},
                {"task_name": "Missing Task", "amount": 50000.0},
            ],
            breakdown_sum=100000.0,
        )
        task_names = {"Existing Task", "Another Task"}

        report = validate_rae_entries([entry], task_names=task_names)

        assert report.has_errors()
        errors = [issue for issue in report.checks if issue.id == "VAL-RAE-005"]
        assert len(errors) == 1
        assert errors[0].severity == ValidationSeverity.ERROR
        assert "Missing Task" in errors[0].message

    def test_validation_passes_when_all_tasks_exist(self) -> None:
        """Given task breakdown with all tasks in XML, validation passes."""
        entry = RAEEntry(
            entry_id=1,
            milestone_name="Phase 1",
            remaining_amount=100000.0,
            forecast_date=date(2026, 3, 31),
            task_breakdown=[
                {"task_name": "Task A", "amount": 50000.0},
                {"task_name": "Task B", "amount": 50000.0},
            ],
            breakdown_sum=100000.0,
        )
        task_names = {"Task A", "Task B", "Task C"}

        report = validate_rae_entries([entry], task_names=task_names)

        assert not report.has_errors()
        rae_005_issues = [issue for issue in report.checks if issue.id == "VAL-RAE-005"]
        assert len(rae_005_issues) == 0


class TestRAEValidationDisplayFormat:
    """Tests for standardized validation display (spec REQ-059)."""

    def test_validation_checks_breakdown_sum(self) -> None:
        """Validation checks if breakdown sum equals remaining amount."""
        entry_match = RAEEntry(
            entry_id=1,
            milestone_name="Phase 1",
            remaining_amount=100000.0,
            forecast_date=date(2026, 3, 31),
            task_breakdown=[
                {"task_name": "Task A", "amount": 50000.0},
                {"task_name": "Task B", "amount": 50000.0},
            ],
            breakdown_sum=100000.0,
        )
        entry_mismatch = RAEEntry(
            entry_id=2,
            milestone_name="Phase 2",
            remaining_amount=100000.0,
            forecast_date=date(2026, 6, 30),
            task_breakdown=[
                {"task_name": "Task C", "amount": 30000.0},
                {"task_name": "Task D", "amount": 20000.0},
            ],
            breakdown_sum=50000.0,
        )

        report_match = validate_rae_entries([entry_match])
        report_mismatch = validate_rae_entries([entry_mismatch])

        assert not report_match.has_errors()
        assert report_mismatch.has_errors()
        mismatch_error = next(
            issue for issue in report_mismatch.checks if issue.id == "VAL-RAE-004"
        )
        assert mismatch_error.severity == ValidationSeverity.ERROR

    def test_validation_checks_milestone_date_match(self) -> None:
        """Validation checks if forecast date matches XML milestone date."""
        entry = RAEEntry(
            entry_id=1,
            milestone_name="Phase 1",
            remaining_amount=100000.0,
            forecast_date=date(2026, 3, 31),
            task_breakdown=[],
            breakdown_sum=0.0,
        )
        milestone_names = {"Phase 1"}
        milestone_dates_match = {"Phase 1": date(2026, 3, 31)}
        milestone_dates_mismatch = {"Phase 1": date(2026, 4, 30)}

        report_match = validate_rae_entries(
            [entry],
            milestone_names=milestone_names,
            milestone_dates=milestone_dates_match,
        )
        report_mismatch = validate_rae_entries(
            [entry],
            milestone_names=milestone_names,
            milestone_dates=milestone_dates_mismatch,
        )

        # Match: no warnings about date mismatch
        assert not report_match.has_errors()
        date_issues_match = [
            issue for issue in report_match.checks if issue.id == "VAL-RAE-006"
        ]
        assert len(date_issues_match) == 0

        # Mismatch: should have warning
        mismatch_warning = next(
            (issue for issue in report_mismatch.checks if issue.id == "VAL-RAE-006"),
            None,
        )
        assert mismatch_warning is not None
        assert mismatch_warning.severity == ValidationSeverity.WARNING
