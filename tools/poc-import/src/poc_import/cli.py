# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""CLI entry point for poc-import."""

import click
from click_shell import shell

from poc_import.commands.help_cmd import help_cmd
from poc_import.commands.msproject import msproject
from poc_import.commands.service import service
from poc_import.commands.xml import xml
from poc_import.shell_state import ShellState


@shell(prompt="> ")
@click.version_option(version="1.0.0", prog_name="poc-import")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Interactive console for import commands."""
    if ctx.obj is None:
        ctx.obj = ShellState()


cli.add_command(msproject)
cli.add_command(xml)
cli.add_command(service)
cli.add_command(help_cmd)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
