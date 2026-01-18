# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""XML inspection commands for the interactive shell."""

from datetime import datetime
from pathlib import Path

import click

from poc_import.cli_support import console, setup_logging
from poc_import.parsers.msproject import MSProjectParser
from poc_import.shell_state import ShellState


@click.group(
    help=(
        "Manipulating XML files and objects.\n\n"
        "Commands:\n"
        "  load  Load an XML file\n"
        "  list  List XML entities (see help xml list)\n"
        "  show  Show XML entities (see help xml show)"
    )
)
def xml() -> None:
    """XML-related commands."""


@xml.command(
    "load",
    help=(
        "Load XML file.\n\n"
        "Parameters:\n"
        "  xml_file  Path to XML file\n\n"
        "Example:\n"
        "  xml load ./my-file.xml"
    ),
)
@click.argument("xml_file", type=click.Path(exists=True, path_type=Path))
@click.pass_obj
def xml_load(state: ShellState, xml_file: Path) -> None:
    """Load an MS Project XML file."""
    setup_logging(verbose=False)
    parser = MSProjectParser(str(xml_file))
    state.data = parser.parse()
    state.xml_path = xml_file
    console.print(f"[green]✓[/green] Loaded: {xml_file}")
    console.print(f"  Project: {state.data.project.name}")
    console.print(f"  Tasks: {len(state.data.tasks)}")


@xml.group(
    "list",
    help=("List XML entities.\n\nCommands:\n  tasks  List project tasks"),
)
def xml_list() -> None:
    """List entities from loaded XML."""


@xml_list.command("tasks", help="List project tasks.")
@click.pass_obj
def xml_list_tasks(state: ShellState) -> None:
    """List project tasks from loaded XML."""
    if not state.data:
        console.print("[red]Error:[/red] No XML loaded. Use `xml load <file>`.")
        return

    for task in state.data.tasks:
        console.print(f"- {task.uid}: {task.name}")


@xml.group(
    "show",
    help=(
        "Show XML entities.\n\n"
        "Commands:\n"
        "  info  Show project information\n"
        "  task  Show task detail\n\n"
        "Example:\n"
        "  xml show task 42"
    ),
)
def xml_show() -> None:
    """Show XML entities from loaded XML."""


@xml_show.command("info", help="Show project information.")
@click.pass_obj
def xml_show_info(state: ShellState) -> None:
    """Show project information from loaded XML."""
    if not state.data:
        console.print("[red]Error:[/red] No XML loaded. Use `xml load <file>`.")
        return

    project_data = state.data.project.model_dump()
    for key, value in project_data.items():
        if isinstance(value, datetime):
            value = value.isoformat()
        console.print(f"{key}: {value}")


@xml_show.command("task", help="Show task detail.")
@click.argument("task_id", type=int)
@click.pass_obj
def xml_show_task(state: ShellState, task_id: int) -> None:
    """Show a single task by UID."""
    if not state.data:
        console.print("[red]Error:[/red] No XML loaded. Use `xml load <file>`.")
        return

    task = next((item for item in state.data.tasks if item.uid == task_id), None)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        return

    task_data = task.model_dump()
    for key, value in task_data.items():
        if isinstance(value, datetime):
            value = value.isoformat()
        console.print(f"{key}: {value}")
