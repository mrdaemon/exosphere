"""
Exosphere Command Line Interface (CLI)

This module provides the main CLI interface for Exosphere, setting up
the interactive REPL and command/subcommand structure.

It handles setting up the CLI environment, loading command modules,
and acts as the CLI entrypoint for the application.
"""

import logging
from collections.abc import Sequence

from cyclopts import App, CycloptsError, Group
from cyclopts.help import DefaultFormatter
from cyclopts.help.specs import PanelSpec

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


# Help panel formatter to use across the app
HELP_FORMATTER = DefaultFormatter(panel_spec=PanelSpec(border_style="dim"))

# Setup the root CLI app
app = App(
    name="exosphere",
    help=ROOT_HELP,
    help_flags=["--help"],
    version=get_version_string,
    version_format="rich",
    version_flags=["--version", "-V"],
    error_formatter=error_formatter,  # Custom formatter
    help_formatter=HELP_FORMATTER,
    console=console,
    error_console=err_console,
)

# Setup commands from modules
for subapp in (
    inventory.app,
    host.app,
    connections.app,
    ui.app,
    config.app,
    report.app,
    sudo.app,
    version.app,
):
    # The REPL calls help directly on subapps at times, so we
    # explicitly set the help formatter on them for consistency.
    # Other scenarios inherit from the root app.
    app.command(subapp)
    subapp.help_formatter = HELP_FORMATTER

# Register the shell completion installer.
app.register_install_completion_command()

# Force root --help, --version and --install-completion flags to be
# part of the parameters group instead of the commands one
# This preserves previous CLI behavior
_root_flags_group = Group("Parameters")
for flag in ("--help", "--version", "--install-completion"):
    app[flag].group = _root_flags_group


def run(tokens: Sequence[str] | None = None, *, help_on_error: bool = False) -> None:
    """
    Run the CLI in non-interactive mode.

    Effectively a wrapper around app(exit_on_error=False), to manage
    return codes explicitly and avoid breaking the contract around
    them that has already been changed twice since Exosphere 1.0.

    Messages from Cyclopts are untouched, still go through formatters,
    and this just gives us control over the return codes to fit our
    documented behaviors, instead of delegating to external deps.

    NOTE: Commands raising CyloptsError (none today, can't foresee any)
          will silently hit SystemExit(1) with no output. This
          limitation is, IMO, not worth alleviating.

    :param tokens: CLI tokens to parse, defaults to ``sys.argv[1:]``
    :param help_on_error: Print the help page before the error
    :raises SystemExit: code 1 (input error) on parsing/validation errors
    """
    try:
        app(tokens, help_on_error=help_on_error, exit_on_error=False)
    except CycloptsError:
        raise SystemExit(1) from None  # Input error


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
