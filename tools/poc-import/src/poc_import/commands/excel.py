# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Excel-related commands for the interactive shell."""

import click

from poc_import.commands.expenses import expenses
from poc_import.commands.rae import rae


@click.group(
    help=(
        "Manipulating Excel files and imports.\n\n"
        "Commands:\n"
        "  expenses  Import expenses from an Excel file\n"
        "  rae       Import RAE from an Excel file"
    )
)
def excel() -> None:
    """Excel-related commands."""


excel.add_command(expenses)
excel.add_command(rae)
