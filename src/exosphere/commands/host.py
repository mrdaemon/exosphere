"""
Host command module
"""

import typer
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from typing_extensions import Annotated

from exosphere import app_config
from exosphere.commands.utils import console, err_console, get_host_or_error
from exosphere.objects import Host

# Reuse the save function from the inventory command
from .inventory import save as save_inventory

# Simple spinner layout for long or pre-tasks
SPINNER_PROGRESS_ARGS = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
)

ROOT_HELP = """
Host Management Commands

Commands to query, refresh and discover individual hosts.
"""

app = typer.Typer(
    help=ROOT_HELP,
    no_args_is_help=True,
)


def _format_security_count(host: Host) -> str:
    """Format security updates count."""
    return f"[red]{len(host.security_updates)}[/red]" if host.security_updates else "0"


def _format_os_details(host: Host) -> str:
    """Format OS details string."""
    if host.flavor and host.flavor != host.os:
        return f"{host.flavor} {host.os} {host.version}"
    else:
        return f"{host.os} {host.version}"


def _format_last_refresh(host: Host) -> str:
    """Format last refresh time."""
    if not host.last_refresh:
        return "[red]Never[/red]"
    else:
        return host.last_refresh.astimezone().strftime("%a %b %d %H:%M:%S %Y")


def _make_host_panel_content(host: Host) -> str:
    """Compose the main panel content for host details."""

    online_status = "[bold green]Online[/bold green]"
    offline_status = "[red]Offline[/red]"

    # Base information always shown
    content = (
        f"[bold]Host Name:[/bold] {host.name}\n"
        f"[bold]IP Address:[/bold] {host.ip}\n"
        f"[bold]Port:[/bold] {host.port}\n"
        "[bold]Online Status:[/bold] "
        f"{online_status if host.online else offline_status}\n"
        "\n"
    )

    # Show specific content for supported and unsupported hosts
    if host.supported:
        content += _make_supported_host_content(host)
    else:
        content += _make_unsupported_host_content(host)

    return content


def _make_supported_host_content(host: Host) -> str:
    """Build content section for supported hosts."""
    security_count = _format_security_count(host)
    os_details = _format_os_details(host)
    last_refresh = _format_last_refresh(host)

    return (
        f"[bold]Operating System:[/bold]\n"
        f"  {os_details}, using {host.package_manager}\n"
        "\n"
        f"[bold]Last Refreshed:[/bold] {last_refresh}\n"
        f"[bold]Stale:[/bold] {'[yellow]Yes[/yellow]' if host.is_stale else 'No'}\n"
        "\n"
        f"[bold]Updates Available:[/bold] {len(host.updates)} updates, {security_count} security\n"
    )


def _make_unsupported_host_content(host: Host) -> str:
    """Build content section for unsupported hosts."""
    return (
        f"[bold]Operating System:[/bold]\n"
        f"  {host.os} [yellow](Unsupported OS)[/yellow]\n"
    )


def _display_updates_table(host: Host, security_only: bool) -> None:
    """Display the updates table for a host."""
    update_list = host.updates if not security_only else host.security_updates

    if not update_list:
        console.print("[bold]No updates available for this host.[/bold]")
        return

    updates_table = Table(
        "Name",
        "Current Version",
        "New Version",
        "Security",
        "Source",
        title="Available Updates",
    )

    for update in update_list:
        updates_table.add_row(
            f"[bold]{update.name}[/bold]",
            update.current_version if update.current_version else "(NEW)",
            update.new_version,
            "Yes" if update.security else "No",
            Text(update.source or "N/A", no_wrap=True),
            style="on bright_black" if update.security else "default",
        )

    console.print(updates_table)


@app.command()
def show(
    name: Annotated[str, typer.Argument(help="Host from inventory to show")],
    include_updates: Annotated[
        bool,
        typer.Option(
            "--updates/--no-updates",
            "-u/-n",
            help="Show update details for the host",
        ),
    ] = True,
    security_only: Annotated[
        bool,
        typer.Option(
            "--security-only",
            "-s",
            help="Show only security updates for the host when displaying updates",
        ),
    ] = False,
) -> None:
    """
    Show details of a specific host.

    This command retrieves the host by name from the inventory
    and displays its details in a rich format.
    """
    host = get_host_or_error(name)
    if host is None:
        raise typer.Exit(code=2)  # Argument error

    # Validate options
    if not include_updates and security_only:
        err_console.print(
            "[red]Error: --security-only option is only valid with --updates.[/red]"
        )
        raise typer.Exit(code=2)  # Argument error

    # Display main host information panel
    panel_content = _make_host_panel_content(host)
    console.print(
        Panel.fit(
            panel_content,
            title=host.description if host.description else "Host Details",
        )
    )

    # Exit early if updates not requested
    if not include_updates:
        raise typer.Exit(code=0)

    # Handle unsupported hosts
    if not host.supported:
        console.print(
            "[yellow]Update info is not available for unsupported hosts.[/yellow]"
        )
        raise typer.Exit(code=0)

    # Display updates table
    _display_updates_table(host, security_only)


@app.command()
def discover(
    name: Annotated[str, typer.Argument(help="Host from inventory to discover")],
) -> None:
    """
    Gather platform data for host.

    This command retrieves the host by name from the inventory
    and synchronizes its platform data, such as OS, version and
    package manager.
    """
    host = get_host_or_error(name)

    if host is None:
        raise typer.Exit(code=2)  # Argument error

    with Progress(*SPINNER_PROGRESS_ARGS) as progress:
        progress.add_task(f"Discovering platform for '{host.name}'", total=None)
        try:
            host.discover()
        except Exception as e:
            progress.console.print(
                Panel.fit(
                    f"{str(e)}",
                    title="[red]Error[/red]",
                    style="red",
                    title_align="left",
                )
            )
            raise typer.Exit(code=1)  # Execution error

    if app_config["options"]["cache_autosave"]:
        save_inventory()


@app.command()
def refresh(
    name: Annotated[str, typer.Argument(help="Host from inventory to refresh")],
    full: Annotated[
        bool, typer.Option("--sync", "-s", help="Also sync package repositories")
    ] = False,
    discover: Annotated[
        bool, typer.Option("--discover", "-d", help="Also refresh platform information")
    ] = False,
) -> None:
    """
    Refresh the updates for a specific host.

    This command retrieves the host by name from the inventory
    and refreshes its available updates.
    """
    host = get_host_or_error(name)

    if host is None:
        raise typer.Exit(code=2)  # Argument error

    with Progress(transient=True, *SPINNER_PROGRESS_ARGS) as progress:
        if discover:
            task = progress.add_task(
                f"Refreshing platform information for '{host.name}'", total=None
            )
            try:
                host.discover()
            except Exception as e:
                progress.console.print(
                    Panel.fit(
                        f"{str(e)}",
                        title="[red]Error[/red]",
                        style="red",
                        title_align="left",
                    )
                )
                progress.stop_task(task)
                raise typer.Exit(code=1)  # Execution error

            progress.stop_task(task)

        if full:
            task = progress.add_task(
                f"Syncing package repositories for '{host.name}'", total=None
            )
            try:
                host.sync_repos()
            except Exception as e:
                progress.console.print(
                    Panel.fit(
                        f"{str(e)}",
                        title="[red]Error[/red]",
                        style="red",
                        title_align="left",
                    )
                )
                progress.stop_task(task)
                raise typer.Exit(code=1)  # Execution error

            progress.stop_task(task)

        task = progress.add_task(f"Refreshing updates for '{host.name}'", total=None)
        try:
            host.refresh_updates()
        except Exception as e:
            progress.console.print(
                Panel.fit(
                    f"{str(e)}",
                    title="[red]Error[/red]",
                    style="red",
                    title_align="left",
                )
            )
            progress.stop_task(task)
            raise typer.Exit(code=1)  # Execution error

    if app_config["options"]["cache_autosave"]:
        save_inventory()


@app.command()
def ping(
    name: Annotated[str, typer.Argument(help="Host from inventory to ping")],
) -> None:
    """
    Ping a specific host to check its reachability.

    This command will also update a host's online status
    based on the ping result.

    The ping status is based on ssh connectivity.
    """
    host = get_host_or_error(name)

    if host is None:
        raise typer.Exit(code=2)  # Argument error

    if host.ping():
        console.print(
            f"Host [bold]{host.name}[/bold] is [bold green]Online[/bold green]."
        )
    else:
        console.print(f"Host [bold]{host.name}[/bold] is [red]Offline[/red].")

    if app_config["options"]["cache_autosave"]:
        save_inventory()
