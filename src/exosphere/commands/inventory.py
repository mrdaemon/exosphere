import logging

import typer
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from typing_extensions import Annotated

from exosphere import app_config, context
from exosphere.inventory import Inventory
from exosphere.objects import Host

# Constants for display
ERROR_STYLE = {
    "style": "bold red",
    "title_align": "left",
}
STATUS_FORMATS = {
    "success": "[[bold green]OK[/bold green]]",
    "failure": "[[bold red]FAILED[/bold red]]",
}
SPINNER_PROGRESS_ARGS = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TaskProgressColumn(),
    TimeElapsedColumn(),
)


app = typer.Typer(
    help="Inventory and Bulk Management Commands",
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


def _get_hosts_or_error(
    names: list[str] | None = None,
) -> list[Host] | None:
    """
    Get hosts from the inventory, filtering by names if provided.
    Will print an error message and return None if all hosts are not found.

    In the absence of names, will return all hosts in the inventory.
    """

    inventory: Inventory = _get_inventory()

    if names:
        hosts_match = [h for h in inventory.hosts if h.name in names]
        unmatched = set(names) - {h.name for h in hosts_match}

        if unmatched:
            err_console.print(
                Panel.fit(
                    f"Hosts not found in inventory: {', '.join(unmatched)}",
                    title="Error",
                )
            )
            return None

        return hosts_match

    # No names provided, return all hosts
    if not inventory.hosts:
        err_console.print(
            Panel.fit(
                "No hosts found in inventory. Ensure your configuration is correct.",
                title="Error",
            )
        )
        return None

    return inventory.hosts


def _run_task_with_progress(
    inventory: Inventory,
    hosts: list[Host],
    task_name: str,
    task_description: str,
    display_hosts: bool = True,
    collect_errors: bool = True,
    immediate_error_display: bool = False,
    transient: bool = True,
    progress_args: tuple = (),
) -> list[tuple[str, str]]:
    """
    Run a task on selected host with progress display
    """
    errors = []
    short_name = task_name.replace("_", " ").capitalize()

    with Progress(transient=transient, *progress_args) as progress:
        task = progress.add_task(task_description, total=len(hosts))

        for host, _, exc in inventory.run_task(task_name, hosts=hosts):
            status_out = STATUS_FORMATS["failure"] if exc else STATUS_FORMATS["success"]
            host_out = f"[bold]{host.name}[/bold]"

            if exc:
                if immediate_error_display:
                    progress.console.print(
                        f"{short_name}: [red]{str(exc)}[/red]",
                    )

                if collect_errors:
                    errors.append((host.name, str(exc)))

            if display_hosts:
                progress.console.print(
                    Columns([status_out, host_out], padding=(2, 1), equal=True)
                )

            progress.update(task, advance=1)

    return errors


@app.command()
def discover(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to discover, all if not specified", metavar="[HOST]..."
        ),
    ] = None,
) -> None:
    """
    Gather platform information for hosts

    On a fresh inventory start, this needs done at least once before
    operations can be performed on the hosts.

    The discover operation will connect to the specified host(s)
    and gather their current state, including Operating System, flavor,
    version and pick a Package Mananager implementation for further
    operations.
    """
    logger = logging.getLogger(__name__)
    logger.info("Gathering platform information for hosts")

    inventory: Inventory = _get_inventory()

    hosts = _get_hosts_or_error(names)

    if hosts is None:
        return

    errors = _run_task_with_progress(
        inventory=inventory,
        hosts=hosts,
        task_name="discover",
        task_description="Gathering platform information",
        display_hosts=True,
        collect_errors=True,
        immediate_error_display=False,
    )

    errors_table = Table(
        "Host", "Error", show_header=False, show_lines=False, box=box.SIMPLE_HEAD
    )

    exit_code = 0

    if errors:
        console.print()
        console.print("The following hosts could not be discovered due to errors:")
        for host, error in errors:
            errors_table.add_row(host, f"[bold red]{error}[/bold red]")

        console.print(errors_table)
        exit_code = 1

    if app_config["options"]["cache_autosave"]:
        save()

    raise typer.Exit(code=exit_code)


@app.command()
def refresh(
    discover: Annotated[
        bool, typer.Option(help="Also refresh platform information")
    ] = False,
    sync: Annotated[
        bool, typer.Option(help="Sync the package repositories as well as updates")
    ] = False,
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to refresh, all if not specified", metavar="[HOST]..."
        ),
    ] = None,
) -> None:
    """
    Refresh the update data for all hosts

    Connects to hosts in the inventory and retrieves pending package
    updates.

    If --discover is specified, the platform information (Operating
    System flavor, version, package manager) will also be refreshed.
    Also refreshes the online status in the process.

    If --sync is specified, the package repositories will also be synced.

    Syncing the package repositories involves invoking whatever mechanism
    the package manager uses to achieve this, and can be a very expensive
    operation, which may take a long time, especially on large inventories
    with a handful of slow hosts.
    """
    logger = logging.getLogger(__name__)
    logger.info("Refreshing inventory data")

    inventory: Inventory = _get_inventory()

    hosts = _get_hosts_or_error(names)

    if hosts is None:
        return

    if discover:
        _run_task_with_progress(
            inventory=inventory,
            hosts=hosts,
            task_name="discover",
            task_description="Gathering platform information",
            display_hosts=False,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
        )

    # If sync is requested, we will run the sync_repos task
    if sync:
        _run_task_with_progress(
            inventory=inventory,
            hosts=hosts,
            task_name="sync_repos",
            task_description="Syncing package repositories",
            display_hosts=False,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
        )

    # Finally, refresh the updates for all hosts
    # We want this one to display the progress bar and summarize errors.
    errors = _run_task_with_progress(
        inventory=inventory,
        hosts=hosts,
        task_name="refresh_updates",
        task_description="Refreshing package updates",
        display_hosts=False,
        collect_errors=True,
        immediate_error_display=False,
    )

    errors_table = Table(
        "Host",
        "Error",
        show_header=False,
        show_lines=False,
        box=box.SIMPLE_HEAD,
        title="Refresh Errors",
    )

    if app_config["options"]["cache_autosave"]:
        save()

    if errors:
        console.print()
        for host, error in errors:
            errors_table.add_row(host, f"[bold red]{error}[/bold red]")

        console.print(errors_table)

        raise typer.Exit(code=1)


@app.command()
def ping(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to ping, all if not specified", metavar="[HOST]..."
        ),
    ] = None,
) -> None:
    """
    Ping all hosts in the inventory

    Attempts to connect to all hosts in the inventory.
    On failure, the affected host will be marked as offline.

    You can use this command to quickly check whether or not
    hosts are reachable and online.

    Invoke this to update the online status of hosts if
    any have gone offline and exosphere refuses to run
    an operation on them.
    """
    logger = logging.getLogger(__name__)
    logger.info("Pinging all hosts in the inventory")

    inventory: Inventory = _get_inventory()

    hosts = _get_hosts_or_error(names)

    if hosts is None:
        logger.error("No host(s) found, aborting")
        return

    with Progress(
        transient=True,
    ) as progress:
        error_count = 0
        task = progress.add_task("Pinging hosts", total=len(hosts))
        for host, status, exc in inventory.run_task("ping", hosts=hosts):
            if status:
                progress.console.print(
                    f"  Host [bold]{host.name}[/bold] is [bold green]online[/bold green]."
                )
            else:
                error_count += 1
                if exc:
                    progress.console.print(
                        f"  Host [bold]{host.name}[/bold]: [bold red]ERROR[/bold red] - {str(exc)}",
                    )
                else:
                    progress.console.print(
                        f"  Host [bold]{host.name}[/bold] is [bold red]offline[/bold red]."
                    )

            progress.update(task, advance=1)

    if app_config["options"]["cache_autosave"]:
        save()

    if error_count > 0:
        raise typer.Exit(code=1)


@app.command()
def status(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to show status for, all if not specified", metavar="[HOST]..."
        ),
    ] = None,
) -> None:
    """
    Show hosts and their status

    Display a nice table with the current state of all the hosts
    in the inventory, including their package update counts, their
    online status and whether or not the data is stale.

    This is the main CLI UI for the inventory.
    """
    logger = logging.getLogger(__name__)
    logger.info("Showing status of all hosts")

    hosts = _get_hosts_or_error(names)
    if hosts is None:
        return

    # Iterates through all hosts in the inventory and render a nice
    # Rich table with their properties and status
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

    for host in hosts:
        # Prepare some rendering data for suffixes and placeholders
        stale_suffix = " [dim]*[/dim]" if host.is_stale else ""
        unknown_status = "[dim](unknown)[/dim]"

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
            host.os or unknown_status,
            host.flavor or unknown_status,
            host.version or unknown_status,
            updates,
            security_updates,
            online_status,
        )

    console.print(table)


@app.command()
def save() -> None:
    """
    Save the current inventory state to disk

    Manually save the current state of the inventory to disk using the
    configured cache file.

    The data is compressed using LZMA.

    If options.cache_autosave is enabled, this will will be automatically
    invoked after every discovery or refresh operation.

    Since this is enabled by default, you will rarely need to invoke this
    manually.

    """
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
            raise typer.Exit(1)

    logger.debug("Inventory save operation completed")


@app.command()
def clear(
    confirm: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Do not prompt for confirmation", prompt=True
        ),
    ],
) -> None:
    """
    Clear the inventory state and cache file

    This will empty the inventory cache file and re-initialize
    all hosts from scratch.

    This is useful if you want to reset the inventory state, or
    have difficulties with stale data that cannot be resolved.

    Note that this will remove all cached host data, so you will
    need to re-discover the entire inventory after this operation.

    """
    inventory: Inventory = _get_inventory()
    if not confirm:
        console.print("Inventory state has [bold]not[/bold] been cleared.")
        raise typer.Exit(1)

    try:
        inventory.clear_state()
    except Exception as e:
        err_console.print(
            Panel.fit(
                f"[bold red]Error clearing inventory state:[/bold red] {e}",
                style="bold red",
            )
        )
        raise typer.Exit(1)
    else:
        console.print(
            Panel.fit(
                "Inventory state has been cleared. "
                "You will need to re-discover the inventory.",
                title="Cache Cleared",
            )
        )
