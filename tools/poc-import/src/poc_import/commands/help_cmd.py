# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Custom help command for interactive shell."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

import click

from poc_import.cli_support import console


def _print_header(title: str) -> None:
    """Print a section header."""
    console.print(title)


def _print_blank_line() -> None:
    """Print a blank line for readability."""
    console.print("")


def _print_command_list(lines: Iterable[str]) -> None:
    """Print a list of command lines."""
    for line in lines:
        console.print(f"  {line}")


class _MultiCommandProto(Protocol):
    """Minimal protocol for Click multi-command APIs."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return available command names."""

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        """Return a command by name."""


def _get_root(ctx: click.Context) -> click.Context:
    """Return the root context for command lookup."""
    return ctx.find_root()


def _get_command(ctx: click.Context, name: str) -> click.Command | None:
    """Get a command by name from the root context."""
    root = _get_root(ctx)
    command = root.command
    if not hasattr(command, "get_command"):
        return None
    multi = cast(_MultiCommandProto, command)
    return multi.get_command(root, name)


def _new_context(command: click.Command) -> click.Context:
    """Create a new click context for command resolution."""
    return click.Context(command)


def _print_root_help(ctx: click.Context) -> None:
    """Print help for the root shell."""
    root = _get_root(ctx)
    command = root.command
    if not hasattr(command, "list_commands"):
        console.print("No commands available.")
        return

    multi = cast(_MultiCommandProto, command)

    _print_header("Commands:")
    names = multi.list_commands(root)
    lines: list[str] = []
    for name in names:
        child = multi.get_command(root, name)
        if child is None or getattr(child, "hidden", False):
            continue
        short_help = child.get_short_help_str() or ""
        lines.append(f"{name}  {short_help}".rstrip())
    _print_command_list(lines)


def _print_xml_help(topic: tuple[str, ...]) -> None:
    """Print structured help for XML commands."""
    if not topic:
        _print_header("Manipulating XML files and objects")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "load  Load an XML file",
                "list  List XML entities (see help xml list)",
                "show  Show XML entities (see help xml show)",
                "validate  Validate XML data",
                "import  Import XML entities (see help xml import)",
            ]
        )
        return

    if topic[0] == "load":
        _print_header("Load XML file")
        _print_blank_line()
        _print_header("Parameters:")
        _print_command_list(["xml_file"])
        _print_blank_line()
        _print_header("Example:")
        console.print("  xml load ./my-file.xml")
        return

    if topic[0] == "list":
        _print_header("List XML entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "tasks: List project tasks",
                "resources: List project resources",
                "assignments: List project assignments",
                "dependencies: List project dependencies",
            ]
        )
        return

    if topic[0] == "show":
        _print_header("Show XML entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "info: Show project informations",
                "task: Show task detail",
                "resource: Show resource detail",
                "assignment: Show assignment detail",
                "dependency: Show dependency detail",
            ]
        )
        _print_blank_line()
        _print_header("Parameters:")
        _print_command_list(
            [
                "task_id",
                "resource_id",
                "assignment_id",
                "dependency_id",
            ]
        )
        _print_blank_line()
        _print_header("Example:")
        console.print("  xml show task <task_id>")
        return

    if topic[0] == "import":
        _print_header("Import XML entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "create-project: Create a project and import data",
                "project: Import full project data",
                "task: Import a single task",
            ]
        )
        return

    console.print(f"Unknown XML help topic: {' '.join(topic)}")


def _print_service_help(topic: tuple[str, ...]) -> None:
    """Print structured help for service commands."""
    if not topic:
        _print_header("Manipulating the wfp-poc service")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "list    List service entities (see help service list)",
                "show    Show service entities (see help service show)",
                "select  Select active project context",
                "delete  Delete service entities (see help service delete)",
                "projects  Project operations (see help service projects)",
                "tasks  Task operations (see help service tasks)",
            ]
        )
        return

    if topic[0] == "list":
        _print_header("List service entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "projects: List projects",
                "tasks: List tasks for selected project",
                "resources: List resources",
                "assignments: List assignments for selected project",
                "dependencies: List dependencies for selected project",
            ]
        )
        return

    if topic[0] == "show":
        _print_header("Show service entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "project: Show selected project",
                "task: Show task by ID",
                "resource: Show resource by ID",
                "assignment: Show assignment by ID",
                "dependency: Show dependency by ID",
            ]
        )
        return

    if topic[0] == "delete":
        _print_header("Delete service entities")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "project: Delete selected project (or pass project_id)",
                "task: Delete task by ID (selected project required)",
                "resource: Delete resource by ID",
                "assignment: Delete assignment by ID (selected project required)",
            ]
        )
        return

    if topic[0] == "projects":
        _print_header("Project operations")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(["list: List projects"])
        return

    if topic[0] == "tasks":
        _print_header("Task operations")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(["list: List tasks for a project"])
        return

    console.print(f"Unknown service help topic: {' '.join(topic)}")


def _print_excel_help(topic: tuple[str, ...]) -> None:
    """Print structured help for Excel commands."""
    if not topic:
        _print_header("Manipulating Excel files and imports")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(
            [
                "load   Load an Excel file",
                "list   List Excel entries",
                "show   Show Excel entries",
                "import Import Excel entries",
            ]
        )
        return

    if topic[0] == "load":
        _print_header("Load Excel data")
        _print_blank_line()
        _print_header("Example:")
        console.print("  excel load ./expenses.xlsx --type expenses")
        console.print("  excel load ./rae.xlsx --type rae")
        return

    if topic[0] == "list":
        _print_header("List Excel entries")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(["expenses", "rae"])
        return

    if topic[0] == "show":
        _print_header("Show Excel entries")
        _print_blank_line()
        _print_header("Commands:")
        _print_command_list(["expense", "rae"])
        return

    if topic[0] == "import":
        _print_header("Import Excel entries")
        _print_blank_line()
        _print_blank_line()
        _print_header("Example:")
        console.print("  excel import expenses --dry-run")
        console.print("  excel import rae --dry-run")
        return

    console.print(f"Unknown excel help topic: {' '.join(topic)}")


@click.command(name="help", help="Show help for a command or topic.")
@click.argument("topic", nargs=-1)
@click.pass_context
def help_cmd(ctx: click.Context, topic: tuple[str, ...]) -> None:
    """Show help for a command or topic."""
    if not topic:
        _print_root_help(ctx)
        return

    if topic[0] == "xml":
        _print_xml_help(topic[1:])
        return

    if topic[0] == "service":
        _print_service_help(topic[1:])
        return

    if topic[0] == "excel":
        _print_excel_help(topic[1:])
        return

    command = _get_command(ctx, topic[0])
    if command is None:
        console.print(f"Command not found: {' '.join(topic)}")
        return

    console.print(command.get_help(_new_context(command)))
