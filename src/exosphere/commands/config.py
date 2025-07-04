import os
from typing import Annotated

import typer
from rich.console import Console

from exosphere import app_config, context
from exosphere.config import Configuration

app = typer.Typer(
    help="Runtime Configuration Commands",
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
        typer.Option(help="Show full configuration structure, including inventory."),
    ] = False,
) -> None:
    """
    Show the current configuration.
    """

    if full:
        if option:
            err_console.print(
                "[yellow]Full configuration requested, ignoring option.[/yellow]"
            )
        console.print(app_config)
        return

    if option:
        if option in app_config["options"]:
            console.print(app_config["options"][option])
        else:
            err_console.print(
                f"[red]Option '{option}' not found in configuration.[/red]"
            )

        return

    console.print(app_config["options"])


@app.command()
def source() -> None:
    """
    Show the configuration source, where it was loaded from

    Displays the path of the configuration file loaded, if any, and
    any environment variables that affect the configuration.
    """

    if context.confpath:
        console.print(f"Configuration loaded from: {context.confpath}")
    else:
        console.print("No configuration loaded, using defaults.")

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
        console.print("Environment variables affecting configuration:\n")
        for line in env_lines:
            console.print(f"  {line}")
        console.print()


@app.command()
def diff():
    """
    Show the differences between the current configuration and the default one.
    """

    default_config = Configuration.DEFAULTS["options"]
    current_config = app_config["options"]

    differences = {}
    keys = set(default_config.keys()).union(current_config.keys())

    for key in keys:
        if default_config[key] != current_config[key]:
            differences[key] = {
                "default": default_config.get(key),
                "current": current_config.get(key),
            }

    if not differences:
        console.print("No differences found between current and default configuration.")
        return

    console.print("Differences between current and default configuration:\n")

    for key, value in differences.items():
        console.print(f"{key}:")
        console.print(f"  [yellow]Default: {value['default']}[/yellow]")
        console.print(f"  [green]Current: {value['current']}[/green]")
        console.print()
