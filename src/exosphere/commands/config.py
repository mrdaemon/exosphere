"""
Config command module
"""

import os
import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from rich.pretty import Pretty
from rich.prompt import Confirm
from rich.text import Text

from exosphere import app_config, context, fspaths
from exosphere.commands.utils import console, err_console
from exosphere.config import Configuration
from exosphere.config import validate as validate_config
from exosphere.editing import EditorError, open_in_editor

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


@app.command
def edit(
    *,
    validate: Annotated[
        bool, Parameter(name=["--validate"], negative="--no-validate")
    ] = True,
) -> int:
    """
    Open the current configuration file in an editor.

    Launches your text editor against the currently loaded
    configuration file. If no configuration file is loaded, the default
    platform path is opened instead, letting you create one from
    scratch.

    The editor to use is determined  from the ``editor`` configuration
    option and then falls back to the ``VISUAL`` and ``EDITOR``
    environment variables, then finally, a platform default.

    Changes do not affect the running process; they take effect on next
    startup. After editing, the file is validated and, if invalid, you
    are offered the chance to re-open the editor and fix it.

    Parameters
    ----------
    validate
        Validate the file after editing (default: enabled).
    """
    # This command is only meaningful in an interactive terminal.
    # In a Non-TTY context, this is fraught with peril, so we just
    # refuse to do it entirely, rather than potentially misbehave.
    if not sys.stdin.isatty():
        err_console.print("This command requires an interactive terminal.")
        return 2  # Application error: wrong context

    if context.confpath:
        target = Path(context.confpath)
    else:
        target = Path(fspaths.CONFIG_DIR) / "config.yaml"
        err_console.print(
            "[yellow]No configuration file is loaded.[/yellow] Opening default path:"
        )
        console.print(f"  {target}\n")

    configured = app_config["options"].get("editor")

    # Only relevant in the REPL: a one-shot CLI invocation exits immediately
    # and the next run reads the file fresh, so there is nothing to restart.
    restart_notice = (
        "Any changes will take effect after you restart Exosphere."
        if context.interactive
        else None
    )

    while True:
        try:
            open_in_editor(target, editor_command=configured)
        except EditorError as e:
            err_console.print(f"[red]{e}[/red]")
            return 1

        if not target.exists():
            console.print("No configuration file was created.")
            return 0

        if not validate:
            if restart_notice:
                console.print(restart_notice)
            return 0

        try:
            validate_config(target)
        except Exception as e:
            err_console.print(f"[red]Configuration is invalid:[/red] {e}")
            if Confirm.ask("Re-open editor to fix?", default=True):
                continue
            err_console.print(
                "Exosphere may fail to start until the configuration is valid."
            )
            return 1

        console.print("[green]Configuration is valid.[/green]")
        if restart_notice:
            console.print(restart_notice)
        return 0
