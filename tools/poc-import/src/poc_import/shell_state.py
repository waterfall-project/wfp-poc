# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Shell session state for interactive commands."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from poc_import.models import MSProjectData


@dataclass
class ShellState:
    """State for interactive shell session."""

    xml_path: Optional[Path] = None
    data: Optional[MSProjectData] = None
