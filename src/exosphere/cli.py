"""
Exosphere Command Line Interface (CLI)

This module provides the main CLI interface for Exosphere, setting up
the interactive REPL and command/subcommand structure.

It handles setting up the CLI environment, loading command modules,
and acts as the CLI entrypoint for the application.
"""

import logging

from cyclopts import App

from exosphere import __version__, app_config
from exosphere.commands import (
    config,
    connections,
    host,
    inventory,
    report,
    sudo,
    ui,
    version,
)
from exosphere.commands.utils import console, err_console, get_version_string
from exosphere.errors import error_formatter
from exosphere.repl import start_repl

BANNER = f"""[turquoise4]                         ▗▖[/turquoise4]
[dark_turquoise]                         ▐▌[/dark_turquoise]
[dark_turquoise] ▟█▙ ▝█ █▘ ▟█▙ ▗▟██▖▐▙█▙ ▐▙██▖ ▟█▙  █▟█▌ ▟█▙[/dark_turquoise]
[medium_turquoise]▐▙▄▟▌ ▐█▌ ▐▛ ▜▌▐▙▄▖▘▐▛ ▜▌▐▛ ▐▌▐▙▄▟▌ █▘  ▐▙▄▟▌[/medium_turquoise]
[dark_turquoise]▐▛▀▀▘ ▗█▖ ▐▌ ▐▌ ▀▀█▖▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘ █   ▐▛▀▀▘[/dark_turquoise]
[dark_turquoise]▝█▄▄▌ ▟▀▙ ▝█▄█▘▐▄▄▟▌▐█▄█▘▐▌ ▐▌▝█▄▄▌ █   ▝█▄▄▌[/dark_turquoise]
[turquoise4] ▝▀▀ ▝▀ ▀▘ ▝▀▘  ▀▀▀ ▐▌▀▘ ▝▘ ▝▘ ▝▀▀  ▀    ▝▀▀[/turquoise4]
[dark_turquoise]                    ▐▌ [bold orange3]v{__version__}[/bold orange3][/dark_turquoise]
"""

ROOT_HELP = """
Exosphere CLI

The main command-line interface for Exosphere. It provides a REPL interface
for interactive use as a prompt, but can also be used to run commands directly
from the command line.

Run without arguments to start the interactive mode.
"""


# Setup the root CLI app
app = App(
    name="exosphere",
    help=ROOT_HELP,
    help_flags=["--help"],
    version=get_version_string,
    version_format="rich",
    version_flags=["--version", "-V"],
    error_formatter=error_formatter,  # Custom formatter
    console=console,
    error_console=err_console,
)

# Setup commands from modules
app.command(inventory.app)
app.command(host.app)
app.command(connections.app)
app.command(ui.app)
app.command(config.app)
app.command(report.app)
app.command(sudo.app)
app.command(version.app)


def start_interactive() -> None:
    """
    Start the interactive REPL.

    This is invoked by the default entrypoint when no command is
    specified, and is called directly.

    It is not setup as a default callback in order to not shadow the
    default handling of "no such command" cases, and still benefit from
    the nice features like fuzzy matching, suggestions, and errors.
    """
    logging.getLogger(__name__).info("Starting Exosphere REPL interface")

    # Print the banner through the shared console
    if not app_config["options"]["no_banner"]:
        console.print(BANNER)

    # Start interactive REPL
    start_repl(app)
