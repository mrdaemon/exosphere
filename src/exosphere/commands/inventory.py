import logging
from typing import Optional

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from typing_extensions import Annotated

from exosphere import app_config, context
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
def sync(
    single_host: Annotated[
        Optional[str],
        typer.Option("--host", "-h", help="Synchronize a specific host by name"),
    ] = None,
) -> None:
    """Synchronize inventory with host state"""
    logger = logging.getLogger(__name__)
    logger.info("Synchronizing inventory with hosts")

    inventory: Inventory = _get_inventory()

    # Host filtering, if applicable
    hosts = (
        [h for h in inventory.hosts if h.name == single_host]
        if single_host
        else inventory.hosts
    )

    if not hosts:
        msg = (
            f"No such host found in inventory: '{single_host}'."
            if single_host
            else "No hosts found in the inventory. Please add hosts to the configuration."
        )

        err_console.print(
            Panel.fit(
                msg,
                title="Inventory Error",
                style="bold red",
            )
        )
        return

    with Progress(
        transient=True,
    ) as progress:
        task = progress.add_task("Syncing hosts", total=len(hosts))
        for host, _, exc in inventory.run_task("sync", hosts=hosts):
            output = []
            if exc:
                output.append("  [[bold red]FAILED[/bold red]]")
            else:
                output.append("  [[bold green]OK[/bold green]]")

            output.append(f"[bold]{host.name}[/bold]")

            if exc:
                output.append(f" - {str(exc)}")

            progress.console.print(
                Columns(
                    output,
                    padding=(2, 1),
                    equal=True,
                ),
            )

            progress.update(task, advance=1)

    if app_config["options"]["cache_autosave"]:
        save()


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
        logger.info("Full refresh requested, including package catalog")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
        ) as progress:
            refresh_task = progress.add_task(
                "Refreshing package catalog on all hosts", total=None
            )
            # TODO: this should use run_all instead so we can display errors
            #       instead of just logging them.
            inventory.refresh_catalog_all()
            progress.stop_task(refresh_task)

    with Progress(
        transient=True,
    ) as progress:
        task = progress.add_task(
            "Refreshing package updates", total=len(inventory.hosts)
        )
        for host, _, exc in inventory.run_task("refresh_updates"):
            output = []
            if exc:
                output.append("  [[bold red]ERROR[/bold red]]")
            else:
                output.append("  [[bold green]OK[/bold green]]")

            output.append(f"[bold]{host.name}[/bold]")

            if exc:
                output.append(f" - {str(exc)}")

            progress.console.print(
                Columns(
                    output,
                    padding=(2, 1),
                    equal=True,
                ),
            )

            progress.update(task, advance=1)

        progress.stop_task(task)

    if app_config["options"]["cache_autosave"]:
        save()


@app.command()
def ping() -> None:
    """Ping all hosts in the inventory"""
    logger = logging.getLogger(__name__)
    logger.info("Pinging all hosts in the inventory")

    inventory: Inventory = _get_inventory()

    with Progress(
        transient=True,
    ) as progress:
        task = progress.add_task("Pinging hosts", total=len(inventory.hosts))
        for host, status, exc in inventory.run_task("ping"):
            if status:
                progress.console.print(
                    f"  Host [bold]{host.name}[/bold] is [bold green]online[/bold green]."
                )
            else:
                if exc:
                    progress.console.print(
                        f"  Host [bold]{host.name}[/bold]: [bold red]ERROR[/bold red] - {str(exc)}",
                    )
                else:
                    progress.console.print(
                        f"  Host [bold]{host.name}[/bold] is [bold red]offline[/bold red]."
                    )

            progress.update(task, advance=1)


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
            Panel.fit(
                "No hosts found in the inventory. Verify your configuration file.",
                style="bold red",
            )
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
        caption="* indicates stale data",
        caption_justify="right",
    )

    for host in inventory.hosts:
        # Prepare some rendering data for suffixes and placeholders
        stale_suffix = " [dim]*[/dim]" if host.is_stale else ""
        unsynced_status = "[dim](unsynced)[/dim]"

        # Prepare the table row data
        updates = f"{len(host.updates)}{stale_suffix}"

        sec_count = len(host.security_updates) if host.security_updates else 0
        security_updates = (
            f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
        ) + stale_suffix

        online_status = (
            "[bold green]Online[/bold green]" if host.online else "[red]Offline[/red]"
        )

        # Construct table
        table.add_row(
            host.name,
            host.os or unsynced_status,
            host.flavor or unsynced_status,
            host.version or unsynced_status,
            updates,
            security_updates,
            online_status,
        )

    console.print(table)


@app.command()
def save() -> None:
    """Save the current inventory state to disk"""
    logger = logging.getLogger(__name__)
    logger.debug("Starting inventory save operation")

    inventory: Inventory = _get_inventory()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Saving inventory state to disk", total=None)

        try:
            inventory.save_state()
            progress.stop_task(task)
        except Exception as e:
            logger.error("Error saving inventory: %s", e)
            progress.stop_task(task)
            progress.console.print(
                Panel.fit(
                    f"[bold red]Error saving inventory state:[/bold red] {e}",
                    style="bold red",
                ),
            )

    logger.debug("Inventory save operation completed")


@app.command()
def clear() -> None:
    """Clear the inventory state and cache file"""
    inventory: Inventory = _get_inventory()

    try:
        inventory.clear_state()
    except Exception as e:
        err_console.print(
            Panel.fit(
                f"[bold red]Error clearing inventory state:[/bold red] {e}",
                style="bold red",
            )
        )
