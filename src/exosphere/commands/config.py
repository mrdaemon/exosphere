"""
Config command module
"""

import os
from typing import Annotated

from cyclopts import App, Parameter
from rich.pretty import Pretty
from rich.text import Text

from exosphere import app_config, context, fspaths
from exosphere.commands.utils import console, err_console
from exosphere.config import Configuration

ROOT_HELP = """
Configuration-related Commands

Commands to inspect the currently loaded configuration.
"""

app = App(name="config", help=ROOT_HELP, help_flags=["--help"])


@app.command
def show(
    option: str | None = None,
    /,
    *,
    full: Annotated[bool, Parameter(name=["--full", "-f"], negative="")] = False,
) -> int:
    """
    Show the current configuration.

    Displays the current configuration options, or the value of a specific option
    if specified.

    If `--full` is specified, it will show the entire configuration structure,
    including the inventory, beyond just the "options" section.

    Parameters
    ----------
    option
        Name of the option to show. All if not specified.
    full
        Show full configuration structure, including inventory.
    """
    if full:
        if option:
            err_console.print(
                "[yellow]Full configuration requested, ignoring option name.[/yellow]"
            )

        console.print(Pretty(app_config, expand_all=True, max_depth=None))

        return 0

    if option:
        if option in app_config["options"]:
            console.print(app_config["options"][option])
        else:
            err_console.print(
                f"[red]Option '{option}' not found in configuration.[/red]"
            )
            return 1  # Input error: unknown option

        return 0

    console.print(Pretty(app_config["options"], expand_all=True))

    return 0


@app.command
def source(*, env: bool = True) -> None:
    """
    Show the configuration source, where it was loaded from.

    Displays the path of the configuration file loaded, if any, and
    any environment variables that affect the configuration.

    Parameters
    ----------
    env
        Show environment variables that affect the configuration.
    """
    if context.confpath:
        console.print(f"{context.confpath}")
    else:
        err_console.print("No configuration loaded, using defaults.")

    if not env:
        return

    env_lines: list[str] = []

    prefix = "EXOSPHERE_OPTIONS_"

    for key, value in os.environ.items():
        if (
            key.startswith(prefix)
            and key.removeprefix(prefix).lower() in app_config["options"]
        ):
            env_lines.append(f"{key}={value}")

    if env_lines:
        console.print()
        console.print("Environment variable overrides:\n")
        for line in env_lines:
            console.print(f"  {line}")
        console.print()


@app.command
def paths() -> None:
    """
    Show the paths of application directories.

    Will display the platform-specific filesystem paths that exosphere
    uses for configuration, state, logs, and cache.
    """
    console.print("Application directories:")
    console.print()

    for name, path in fspaths.get_dirs().items():
        console.print(f"  {name.capitalize()}: {path}")

    console.print()

    if context.confpath:
        console.print(f"Current configuration file path: {context.confpath}")
    else:
        err_console.print("No configuration file loaded.")


@app.command
def diff(
    *,
    full: Annotated[bool, Parameter(name=["--full", "-f"], negative="")] = False,
) -> None:
    """
    Show the differences between the current configuration and the defaults.

    Exosphere follows convention over configuration, so your configuration
    file can exclusively contain the options you want to change.

    This command allows you to see exactly what has been changed, optionally
    in its context, using the `--full` option.

    For a full config dump, use the `show` command instead.

    Parameters
    ----------
    full
        Show full configuration diff, including unmodified options.
    """
    default_config = Configuration.DEFAULTS["options"]
    current_config = app_config["options"]

    for key in set(default_config) | set(current_config):
        if default_config.get(key, None) != current_config.get(key, None):
            break
    else:
        console.print("No differences found between current and default configuration.")
        return

    lines = []
    for key in sorted(set(default_config) | set(current_config)):
        default_value = default_config.get(key, None)
        current_value = current_config.get(key, None)

        line: Text | None

        if default_value != current_value:
            line = Text(f"{key!r}: {current_value!r},", style="bold green")
            line.append(f"  # default: {default_value!r}", style="yellow")
        else:
            line = Text(f"{key!r}: {current_value!r},", style="dim") if full else None

        if line:
            lines.append(line)

    console.print("{")
    for line in lines:
        console.print("    ", end="")
        console.print(line)
    console.print("}")
