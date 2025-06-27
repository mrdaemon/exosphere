import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Column, Table
from typing_extensions import Annotated

from exosphere import app_config, context
from exosphere.objects import Host

# Steal the save function from inventory command
from .inventory import save as save_inventory

app = typer.Typer(
    help="Host management commands",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


def _get_inventory():
    """
    Get the inventory from context
    A convenience wrapper that bails if the inventory is not initialized.
    """
    if context.inventory is None:
        typer.echo(
            "Inventory is not initialized, are you running this module directly?",
            err=True,
        )
        raise typer.Exit(code=1)

    return context.inventory


def _get_host(name: str) -> Host | None:
    """
    Wraps inventory.get_host() to handle displaying errors on console
    """

    inventory = _get_inventory()

    host = inventory.get_host(name)

    if host is None:
        err_console.print(
            Panel.fit(
                f"Host '{name}' not found in inventory.",
                title="Error",
                style="red",
            )
        )
        return None

    return host


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
    host = _get_host(name)

    if host is None:
        raise typer.Exit(code=1)

    # Color security updates count
    security_count = (
        f"[red]{len(host.security_updates)}[/red]" if host.security_updates else "0"
    )

    # prepare host OS details
    host_os_details = (
        f"{host.flavor} {host.os} {host.version}"
        if host.flavor != host.os
        else f"{host.os} {host.version}"
    )

    if not host.last_refresh:
        last_refresh = "[red]Never[/red]"
    else:
        # Format: "Fri May 21:04:43 EDT 2025"
        last_refresh = host.last_refresh.strftime("%a %b %d %H:%M:%S %Y")

    # Display host properties in a rich panel
    console.print(
        Panel.fit(
            f"[bold]Host Name:[/bold] {host.name}\n"
            f"[bold]IP Address:[/bold] {host.ip}\n"
            f"[bold]Port:[/bold] {host.port}\n"
            f"[bold]Online Status:[/bold] {'[bold green]Online[/bold green]' if host.online else '[red]Offline[/red]'}\n"
            "\n"
            f"[bold]Last Refreshed:[/bold] {last_refresh}\n"
            f"[bold]Stale:[/bold] {'[yellow]Yes[/yellow]' if host.is_stale else 'No'}\n"
            "\n"
            f"[bold]Operating System:[/bold]\n"
            f"  {host_os_details}, using {host.package_manager}\n"
            "\n"
            f"[bold]Updates Available:[/bold] {len(host.updates)} updates, {security_count} security\n",
            title=host.description if host.description else "Host Details",
        )
    )

    if not include_updates:
        # Warn for invalid set of arguments
        if security_only:
            err_console.print(
                "[yellow]Warning: --security-only option is only valid with --updates, ignoring.[/yellow]"
            )

        raise typer.Exit(code=0)

    update_list = host.updates if not security_only else host.security_updates

    # Display updates in a rich table, if any
    if not update_list:
        console.print("[bold]No updates available for this host.[/bold]")
        raise typer.Exit(code=0)

    updates_table = Table(
        "Name",
        "Current Version",
        "New Version",
        "Security",
        Column(header="Source", no_wrap=True),
        title="Available Updates",
    )

    for update in update_list:
        updates_table.add_row(
            f"[bold]{update.name}[/bold]",
            update.current_version if update.current_version else "(NEW)",
            update.new_version,
            "Yes" if update.security else "No",
            update.source or "N/A",
            style="on bright_black" if update.security else "default",
        )

    console.print(updates_table)


@app.command()
def discover(
    name: Annotated[str, typer.Argument(help="Host from inventory to discover")],
) -> None:
    """
    Gather platform data for host.

    This command retrieves the host by name from the inventory
    and synchronizes its platform data.
    """
    host = _get_host(name)

    if host is None:
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    ) as progress:
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

    if app_config["options"]["cache_autosave"]:
        save_inventory()


@app.command()
def refresh(
    name: Annotated[str, typer.Argument(help="Host from inventory to refresh")],
    full: Annotated[
        bool, typer.Option("--sync", "-s", help="Also refresh package catalog")
    ] = False,
    discover: Annotated[
        bool, typer.Option("--discover", "-d", help="Also refresh platform information")
    ] = False,
) -> None:
    """
    Refresh the updates for a specific host.

    This command retrieves the host by name from the inventory
    and refreshes its updates.
    """
    host = _get_host(name)

    if host is None:
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    ) as progress:
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
                raise typer.Exit(code=1)

            progress.stop_task(task)

        if full:
            task = progress.add_task(
                f"Refreshing updates and package catalog for '{host.name}'", total=None
            )
            try:
                host.refresh_catalog()
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
                raise typer.Exit(code=1)

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

    The ping is is based on ssh connectivity.
    """
    host = _get_host(name)

    if host is None:
        raise typer.Exit(code=1)

    if host.ping():
        console.print(
            f"Host [bold]{host.name}[/bold] is [bold green]Online[/bold green]."
        )
    else:
        console.print(f"Host [bold]{host.name}[/bold] is [red]Offline[/red].")

    if app_config["options"]["cache_autosave"]:
        save_inventory()
