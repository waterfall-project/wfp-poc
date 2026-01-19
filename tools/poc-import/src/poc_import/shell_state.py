# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shell session state for interactive commands."""

from dataclasses import dataclass
from pathlib import Path

from poc_import.models import MSProjectData


@dataclass
class ShellState:
    """State for interactive shell session."""

    xml_path: Path | None = None
    data: MSProjectData | None = None
    selected_project_id: str | None = None
    selected_project_name: str | None = None
