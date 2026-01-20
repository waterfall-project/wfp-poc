# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shell session state for interactive commands."""

from dataclasses import dataclass
from pathlib import Path

from poc_import.models import (
    ExcelExpensesData,
    ExcelFileType,
    ExcelRAEData,
    MSProjectData,
)
from poc_import.validators import ValidationReport


@dataclass
class ShellState:
    """State for interactive shell session."""

    xml_path: Path | None = None
    data: MSProjectData | None = None
    selected_project_id: str | None = None
    selected_project_name: str | None = None
    excel_path: Path | None = None
    excel_type: ExcelFileType | None = None
    expenses_data: ExcelExpensesData | None = None
    rae_data: ExcelRAEData | None = None
    excel_report: ValidationReport | None = None
