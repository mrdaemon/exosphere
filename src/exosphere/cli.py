"""
Exosphere Command Line Interface (CLI)

This module provides the main CLI interface for Exosphere, setting up
the interactive REPL and command/subcommand structure.

It handles setting up the CLI environment, loading command modules,
and acts as the CLI entrypoint for the application.
"""

import logging
from typing import Annotated

from rich import print
from rich.console import Console
from typer import Context, Exit, Option, Typer

from exosphere import __version__
from exosphere.commands import config, host, inventory, sudo, ui
from exosphere.repl import start_repl

banner = f"""[turquoise4]
                         ▗▖
                         ▐▌
 ▟█▙ ▝█ █▘ ▟█▙ ▗▟██▖▐▙█▙ ▐▙██▖ ▟█▙  █▟█▌ ▟█▙
▐▙▄▟▌ ▐█▌ ▐▛ ▜▌▐▙▄▖▘▐▛ ▜▌▐▛ ▐▌▐▙▄▟▌ █▘  ▐▙▄▟▌
▐▛▀▀▘ ▗█▖ ▐▌ ▐▌ ▀▀█▖▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘ █   ▐▛▀▀▘
▝█▄▄▌ ▟▀▙ ▝█▄█▘▐▄▄▟▌▐█▄█▘▐▌ ▐▌▝█▄▄▌ █   ▝█▄▄▌
 ▝▀▀ ▝▀ ▀▘ ▝▀▘  ▀▀▀ ▐▌▀▘ ▝▘ ▝▘ ▝▀▀  ▀    ▝▀▀
                    ▐▌ [green]v{__version__}[/green][/turquoise4]
"""

app = Typer(
    no_args_is_help=False,
)

# Setup commands from modules
app.add_typer(inventory.app, name="inventory")
app.add_typer(host.app, name="host")
app.add_typer(ui.app, name="ui")
app.add_typer(config.app, name="config")
app.add_typer(sudo.app, name="sudo")


@app.callback(invoke_without_command=True)
def cli(
    ctx: Context,
    version: Annotated[
        bool, Option("--version", "-V", help="Show version and exit")
    ] = False,
) -> None:
    """
    Exosphere CLI

    The main command-line interface for Exosphere.
    It provides a REPL interface for interactive use as a prompt, but can
    also be used to run commands directly from the command line.

    Run without arguments to start the interactive mode.
    """

    if version:
        print(f"Exosphere version {__version__}")
        raise Exit(0)

    if ctx.invoked_subcommand is None:
        logger = logging.getLogger(__name__)
        logger.info("Starting Exosphere REPL interface")

        # Print the banner using Console for better Unicode support
        console = Console()
        console.print(banner)

        # Start interactive REPL
        start_repl(ctx, prompt_text="exosphere> ")
        Exit(0)
