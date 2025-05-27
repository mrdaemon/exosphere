import logging

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from exosphere import context
from exosphere.inventory import Inventory

app = typer.Typer(
    help="Inventory and Hosts Management Commands",
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


@app.command()
def sync() -> None:
    """Synchronize inventory with host state"""
    logger = logging.getLogger(__name__)
    logger.info("Synchronizing inventory with hosts")

    # Sync all hosts in the inventory
    _get_inventory().sync_all()

    console.print("[bold green]Done![/bold green]")


@app.command()
def refresh(
    full: Annotated[
        bool, typer.Option(help="Refresh the package catalog as well as updates")
    ] = False,
) -> None:
    """Refresh the update data for all hosts"""
    logger = logging.getLogger(__name__)
    logger.info("Refreshing inventory data")

    inventory: Inventory = _get_inventory()

    if full:
        inventory.refresh_catalog_all()

    # Refresh package catalog and updates
    inventory.refresh_updates_all()

    console.print("[bold green]Done![/bold green]")


@app.command()
def ping() -> None:
    """Ping all hosts in the inventory"""
    logger = logging.getLogger(__name__)
    logger.info("Pinging all hosts in the inventory")

    inventory: Inventory = _get_inventory()

    for host, status, exc in inventory.run_all("ping"):
        if status:
            console.print(
                f"Host [bold]{host.name}[/bold] is [bold green]online[/bold green]."
            )
        else:
            if exc:
                console.print(
                    f"Host [bold]{host.name}[/bold]: [bold red]ERROR[/bold red] - {exc}",
                )
            else:
                console.print(
                    f"Host [bold]{host.name}[/bold] is [bold red]offline[/bold red]."
                )


@app.command()
def status() -> None:
    """Show all hosts and their status"""
    logger = logging.getLogger(__name__)
    logger.info("Showing status of all hosts")

    inventory: Inventory = _get_inventory()

    # Iterates through all hosts in the inventory and render a nice
    # Rich table with their properties and status
    if len(inventory.hosts) == 0:
        err_console.print(
            "No hosts found in the inventory. Verify your configuration file.",
            style="bold red",
        )
        return

    table = Table(
        "Host",
        "OS",
        "Flavor",
        "Version",
        "Updates",
        "Security",
        "Status",
        title="Host Status Overview",
    )

    for host in inventory.hosts:
        sec_count = len(host.security_updates) if host.security_updates else 0
        security_updates = (
            f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
        )
        online_status = (
            "[bold green]Online[/bold green]"
            if host.online
            else "[bold red]Offline[/bold red]"
        )

        table.add_row(
            host.name,
            host.os or "(unsynced)",
            host.flavor or "(unsynced)",
            host.version or "(unsynced)",
            str(len(host.updates)),
            security_updates,
            online_status,
        )

    console.print(table)
