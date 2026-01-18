# Copyright (c) 2026 Waterfall Project
# SPDX-License-Identifier: Commercial

"""Hidden shell commands."""

import sys

import click


@click.command(name="exit", hidden=True)
@click.pass_context
def exit_shell(ctx: click.Context) -> None:
    """Exit the interactive shell."""
    ctx.exit(0)
    sys.exit(0)


@click.command(name="quit", hidden=True)
@click.pass_context
def quit_shell(ctx: click.Context) -> None:
    """Exit the interactive shell."""
    ctx.exit(0)
    sys.exit(0)
