"""
Config command module
"""

import os
from typing import Annotated

import typer
from rich.console import Console
from rich.pretty import Pretty
from rich.text import Text

from exosphere import app_config, context, fspaths
from exosphere.config import Configuration

app = typer.Typer(
    help="Configuration related commands",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


@app.command()
def show(
    option: Annotated[
        str | None,
        typer.Argument(help="Name of the option to show. All if not specified."),
    ] = None,
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            "-f",
            help="Show full configuration structure, including inventory.",
        ),
    ] = False,
) -> None:
    """
    Show the current configuration.

    Displays the current configuration options, or the value of a specific option
    if specified.

    If `--full` is specified, it will show the entire configuration structure,
    including the inventory, beyond just the "options" section.
    """

    if full:
        if option:
            err_console.print(
                "[yellow]Full configuration requested, ignoring option name.[/yellow]"
            )
        console.print(Pretty(app_config, expand_all=True, max_depth=None))
        return

    if option:
        if option in app_config["options"]:
            console.print(app_config["options"][option])
        else:
            err_console.print(
                f"[red]Option '{option}' not found in configuration.[/red]"
            )
            raise typer.Exit(1)

        return

    console.print(Pretty(app_config["options"], expand_all=True))


@app.command()
def source(
    env: Annotated[
        bool,
        typer.Option(
            help="Show environment variables that affect the configuration.",
        ),
    ] = True,
) -> None:
    """
    Show the configuration source, where it was loaded from.

    Displays the path of the configuration file loaded, if any, and
    any environment variables that affect the configuration.
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


@app.command()
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


@app.command()
def diff(
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            "-f",
            help="Show full configuration diff, including unmodified options.",
        ),
    ] = False,
):
    """
    Show the differences between the current configuration and the defaults.

    Exosphere follows convention over configuration, so your configuration
    file can exclusively contain the options you want to change.

    This command allows you to see exactly what has been changed, optionally
    in its context, using the `--full` option.

    For a full config dump, use the `show` command instead.
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
