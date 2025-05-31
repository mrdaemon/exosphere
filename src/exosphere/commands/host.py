import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from typing_extensions import Annotated

from exosphere import context
from exosphere.objects import Host

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
    Get a Host object by name from the inventory.
    If the host is not found, it returns None and prints an error message.

    :param name: The name of the host to retrieve, eg "webserver1"
    """
    inventory = _get_inventory()

    # Get the host by host.name from inventory.hosts
    host = next((h for h in inventory.hosts if h.name == name), None)

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
            "--updates",
            "-u",
            help="Show update details for the host",
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
            title="Details",
        )
    )

    if not include_updates:
        raise typer.Exit(code=0)

    # Display updates in a rich table, if any
    if not host.updates:
        console.print("[bold]No updates available for this host.[/bold]")
        raise typer.Exit(code=0)

    updates_table = Table(
        "Name",
        "Current Version",
        "New Version",
        "Security",
        "Source",
        title="Available Updates",
    )

    for update in host.updates:
        updates_table.add_row(
            f"[bold]{update.name}[/bold]",
            update.current_version,
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
                    f"Failed to discover host '{host.name}': {e}",
                    title="Error",
                    style="red",
                )
            )

    save_inventory()


@app.command()
def refresh(
    name: Annotated[str, typer.Argument(help="Host from inventory to refresh")],
    full: Annotated[
        bool, typer.Option("--full", "-f", help="Also refresh package catalog")
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
        if full:
            task = progress.add_task(
                f"Refreshing updates and package catalog for '{host.name}'", total=None
            )
            try:
                host.refresh_catalog()
            except Exception as e:
                progress.console.print(
                    Panel.fit(
                        f"Failed to refresh updates and package catalog for '{host.name}': {e}",
                        title="Error",
                        style="red",
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
                    f"Failed to refresh updates for '{host.name}': {e}",
                    title="Error",
                    style="red",
                )
            )

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

    save_inventory()
