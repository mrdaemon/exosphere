"""
Exosphere Command Line Interface (CLI)

This module provides the main CLI interface for Exosphere, setting up
the interactive REPL and command/subcommand structure.

It handles setting up the CLI environment, loading command modules,
and acts as the CLI entrypoint for the application.
"""

import logging
import sys
from typing import Annotated

# ------------------win32 readline monkeypatch---------------------
if sys.platform == "win32":
    try:
        # On windows, we use a wrapper module for pyreadline3 in order
        # to provide readline compatibility.
        from exosphere.compat import win32readline as readline

        # This needs monkeypatched in order for click_shell to make use
        # of it instead of its internal, broken, legacy pyreadline.
        sys.modules["readline"] = readline
    except ImportError:
        sys.stderr.write(
            "Warning: pyreadline3 not found. "
            "Interactive shell may not enable all features.\n"
        )
# -----------------------------------------------------------------

from click_shell import make_click_shell
from rich import print
from rich.panel import Panel
from typer import Argument, Context, Exit, Option, Typer

from exosphere import __version__
from exosphere.commands import config, host, inventory, sudo, ui

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


@app.command(hidden=True)
def help(ctx: Context, command: Annotated[str | None, Argument()] = None):
    """
    Help for interactive REPL use

    Provides help for the root REPL command when used interactively,
    in a way that is friendler for that specific context.
    If a command is specified, it will show help for that command.

    This only applies when in the interactive REPL, commands (including
    the root 'exosphere' program) will use the standard Typer help
    system when invoked from the command line or non-interactively.
    """

    msg = "\nUse '<command> --help' or 'help <command>' for help on a specific command."

    # Show root help if no command is specified
    if not command:
        if ctx.parent and getattr(ctx.parent, "command", None):
            subcommands = getattr(ctx.parent.command, "commands", {})
            lines = []
            for name, cmd in subcommands.items():
                if cmd.hidden:
                    continue
                lines.append(
                    f"[cyan]{name:<11}[/cyan] {cmd.help or 'No description available.'}"
                )
            content = "\n".join(lines)
            panel = Panel.fit(
                content,
                title="Commands",
                title_align="left",
            )
            print("\nAvailable modules during interactive use:\n")
            print(panel)
        print(msg)
        return

    # Show command help if one is specified
    subcommand = None
    if ctx.parent and getattr(ctx.parent, "command", None):
        subcommands = getattr(ctx.parent.command, "commands", None)
        subcommand = subcommands.get(command) if subcommands else None
        if subcommand:
            subcommand.get_help(ctx)
            print(f"\nUse '{str(subcommand.name)} <command> --help' for more details.")
            return

    # Fall through for unknown commands
    print(f"[red]Unkown command '{command}'[/red]")
    print(msg)


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

        # Print the banner
        print(banner)

        # Start interactive REPL
        repl = make_click_shell(
            ctx,
            prompt="exosphere> ",
        )
        repl.cmdloop()
        Exit(0)
