"""
Version command module

Commands to display and check the current version of Exosphere.
"""

import json
import urllib.request
from typing import Annotated
from urllib.error import URLError

import typer
from packaging.version import parse

from exosphere import __version__, app_config

from .utils import console, err_console, print_environment, print_version

ROOT_HELP = """
Version and Update Check Commands

Show current version, check for updates.
"""

app = typer.Typer(
    help=ROOT_HELP,
    no_args_is_help=False,
)

PACKAGE_NAME = "exosphere-cli"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
RELEASE_URL = "https://github.com/mrdaemon/exosphere/releases/tag/"
DOCS_URL = (
    "https://exosphere.readthedocs.io/en/stable/installation.html#updating-exosphere"
)


@app.callback(invoke_without_command=True)
def version_default(ctx: typer.Context) -> None:
    """
    Show the current version of Exosphere.

    Displays the currently installed version. Use 'version check' to check
    for updates on PyPI.
    """
    if ctx.invoked_subcommand is None:
        print_version()
        raise typer.Exit(0)


@app.command()
def details() -> None:
    """
    Show detailed version and environment information

    Displays the currently installed version along with Python version,
    virtual environment status, and operating system details.
    """
    print_environment()
    raise typer.Exit(0)


@app.command()
def check(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show verbose output for check"),
    ] = False,
) -> None:
    """
    Check for exosphere updates

    Compares the current installed version with the latest version available
    on PyPI and reports if an update is available.

    Exits with code 3 if an update is available.
    """
    current_version = __version__
    if not app_config["options"]["update_checks"]:
        err_console.print(
            "[yellow]Update checks are disabled via configuration.[/yellow]\n"
            "Updates may be managed by your package manager or system administrator."
        )
        raise typer.Exit(0)

    if verbose:
        console.print(f"Current version: [cyan]{current_version}[/cyan]")
        console.print(f"Checking PyPI for latest version of {PACKAGE_NAME}...")

    try:
        # Query PyPI API for package information
        with urllib.request.urlopen(PYPI_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            latest_version = data["info"]["version"]

        if verbose:
            console.print(f"Latest version on PyPI: [cyan]{latest_version}[/cyan]")

        # Parse out versions
        current = parse(current_version)
        latest = parse(latest_version)

        # Compare versions
        if current < latest:
            console.print(
                f"[yellow]![/yellow] A new version is available: "
                f"[bold green]{latest_version}[/bold green] "
                f"(current: [dim]{current_version}[/dim])\n"
                f"\nFor release notes and instructions see: \n"
                f"{RELEASE_URL}v{latest_version}\n"
                f"{DOCS_URL}"
            )

            # Exit with nonzero to indicate update available
            raise typer.Exit(3)
        elif current > latest:
            console.print(
                f"[blue]*[/blue] You are using a development version: "
                f"[blue]{current_version}[/blue] "
                f"(latest stable: [dim]{latest_version}[/dim])"
            )
            raise typer.Exit(0)
        else:
            console.print(
                f"You are using the latest version: "
                f"[bold green]{current_version}[/bold green]"
            )
            raise typer.Exit(0)

    except typer.Exit:
        raise
    except URLError as e:
        err_console.print(f"[red]Error:[/red] Failed to check for updates: {e}")
        err_console.print("[yellow]Please check internet connectivity.[/yellow]")
        raise typer.Exit(1)
    except KeyError as e:
        err_console.print(
            f"[red]Error:[/red] Unexpected response from PyPI API (missing key: {e})"
        )
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] Failed to check for updates: {e}")
        raise typer.Exit(1)
