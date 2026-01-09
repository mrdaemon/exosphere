"""
Inventory command module
"""

import logging

import typer
from rich import box
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

from exosphere import app_config
from exosphere.commands.utils import (
    HostArgument,
    console,
    err_console,
    get_hosts_or_error,
    get_inventory,
    run_task_with_progress,
)
from exosphere.inventory import Inventory

# Constants for display
ERROR_STYLE = {
    "style": "bold red",
    "title_align": "left",
}

SPINNER_PROGRESS_ARGS = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TaskProgressColumn(),
    TimeElapsedColumn(),
)

ROOT_HELP = """
Inventory and Bulk Management Commands

Commands to bulk query, discover and refresh hosts in the inventory.
Most commands acccept an optional list of host names to operate on.
"""

app = typer.Typer(
    help=ROOT_HELP,
    no_args_is_help=True,
)


@app.command()
def discover(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to discover, all if not specified", metavar="[HOST]..."
        ),
        HostArgument(multiple=True),
    ] = None,
) -> None:
    """
    Gather platform information for hosts

    On a fresh inventory start, this needs done at least once before
    operations can be performed on the hosts. It can also be used to
    refresh this information if it has changed, or if a new provider
    has been added to Exosphere.

    The discover operation will connect to the specified host(s)
    and gather their current state, including Operating System, flavor,
    version and pick a Package Manager implementation for further
    operations.
    """
    logger = logging.getLogger(__name__)
    logger.info("Gathering platform information for hosts")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_error(names)

    if hosts is None:
        raise typer.Exit(2)  # Argument error

    errors = run_task_with_progress(
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
        exit_code = 1  # Execution error

    if app_config["options"]["cache_autosave"]:
        save()

    raise typer.Exit(code=exit_code)


@app.command()
def refresh(
    discover: Annotated[
        bool, typer.Option("-d", "--discover", help="Also refresh platform information")
    ] = False,
    sync: Annotated[
        bool,
        typer.Option(
            "-s", "--sync", help="Sync the package repositories as well as updates"
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show verbose output during operations"),
    ] = False,
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to refresh, all if not specified", metavar="[HOST]..."
        ),
        HostArgument(multiple=True),
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

    By default, only the progress bar is shown during the operation.
    If --verbose is specified, the name and completion status of each host
    will be shown in real time.
    """
    logger = logging.getLogger(__name__)
    logger.info("Refreshing inventory data")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_error(names)

    if hosts is None:
        raise typer.Exit(2)  # Argument error

    # Start with discovery, if requested.
    # Displays a simple spinner with no ETA, and no progress bar.
    if discover:
        console.print("[dim]Discovery:[/dim]") if verbose else None
        run_task_with_progress(
            inventory=inventory,
            hosts=hosts,
            task_name="discover",
            task_description="Gathering platform information",
            display_hosts=verbose,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
        )
        console.print() if verbose else None

    # If sync is requested, we will run the sync_repos task
    # Same as discovery, simple spinner
    if sync:
        console.print("[dim]Repository Sync:[/dim]") if verbose else None
        run_task_with_progress(
            inventory=inventory,
            hosts=hosts,
            task_name="sync_repos",
            task_description="Syncing package repositories",
            display_hosts=verbose,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
        )
        console.print() if verbose else None

    # Finally, refresh the updates for all hosts
    # We want this one to display the progress bar and summarize errors.
    console.print("[dim]Updates Refresh:[/dim]") if verbose else None
    errors = run_task_with_progress(
        inventory=inventory,
        hosts=hosts,
        task_name="refresh_updates",
        task_description="Refreshing package updates",
        display_hosts=verbose,
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

        raise typer.Exit(code=1)  # Execution error


@app.command()
def ping(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to ping, all if not specified", metavar="[HOST]..."
        ),
        HostArgument(multiple=True),
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

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_error(names)

    if hosts is None:
        logger.error("No host(s) found, aborting")
        raise typer.Exit(2)  # Argument error

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
        raise typer.Exit(code=1)  # Execution error


@app.command()
def status(
    updates_only: Annotated[
        bool,
        typer.Option(
            "-u",
            "--updates-only",
            help="Show only hosts with pending updates",
        ),
    ] = False,
    security_only: Annotated[
        bool,
        typer.Option(
            "-s",
            "--security-only",
            help="Show only hosts with pending security updates (implies --updates-only)",
        ),
    ] = False,
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Host(s) to show status for, all if not specified", metavar="[HOST]..."
        ),
        HostArgument(multiple=True),
    ] = None,
) -> None:
    """
    Show hosts and their status

    Display a nice table with the current state of all the hosts
    in the inventory, including their package update counts, their
    online status and whether or not the data is stale.

    Output can be filtered to only show hosts with pending
    updates or security updates. Filtering for security updates
    implies filtering for updates as well.

    No matches when filtering will exit with code 3.
    """
    logger = logging.getLogger(__name__)
    logger.info("Showing status of all hosts")

    hosts = get_hosts_or_error(names)
    if hosts is None:
        raise typer.Exit(2)  # Argument error

    # Apply filters and set table title based on active flags
    # Note: security_only implies updates_only as they're a subset,
    # so it effectively takes precedence here.
    match (updates_only, security_only):
        case (_, True):
            table_suffix = "(security updates only)"
            hosts = [host for host in hosts if host.security_updates]
        case (True, False):
            table_suffix = "(updates only)"
            hosts = [host for host in hosts if host.updates]
        case _:
            table_suffix = "Overview"

    if not hosts:
        console.print(Panel.fit("No hosts matching requested criteria."))
        raise typer.Exit(3)  # No matches for filtering

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
        title=f"Host Status {table_suffix}",
        caption="* indicates stale data",
        caption_justify="right",
    )

    for host in hosts:
        # Prepare some rendering data for suffixes and placeholders
        stale_suffix = " [dim]*[/dim]" if host.is_stale else ""
        unknown_status = "[dim](unknown)[/dim]"
        unsupported_status = "[dim](unsupported)[/dim]"
        empty_placeholder = "[dim]—[/dim]"

        # Prepare table row data
        if host.supported:
            updates = f"{len(host.updates)}{stale_suffix}"

            sec_count = len(host.security_updates) if host.security_updates else 0
            security_updates = (
                f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
            ) + stale_suffix
        else:
            # Do not show update counts for unsupported hosts
            updates = empty_placeholder
            security_updates = empty_placeholder

        online_status = (
            "[bold green]Online[/bold green]" if host.online else "[red]Offline[/red]"
        )

        # Handle platform info display with unsupported status
        def get_platform_info(value):
            if value:
                return value
            elif host.online and not host.supported:
                return unsupported_status
            else:
                return unknown_status

        # Construct table
        table.add_row(
            host.name,
            get_platform_info(host.os),
            get_platform_info(host.flavor),
            get_platform_info(host.version),
            updates,
            security_updates,
            online_status,
        )

    console.print(table)


@app.command(hidden=True)  # Interactive-only command
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

    This command is only available in interactive mode, as the inventory
    state is not persisted between separate CLI invocations when autosave
    is disabled.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Starting inventory save operation")

    inventory: Inventory = get_inventory()

    with Progress(
        *SPINNER_PROGRESS_ARGS,
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
            raise typer.Exit(1)  # Execution error

    logger.debug("Inventory save operation completed")


@app.command()
def clear(
    confirm: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Do not prompt for confirmation",
            prompt="Clear inventory state?",
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
    inventory: Inventory = get_inventory()
    if not confirm:
        console.print("Inventory state has [bold]not[/bold] been cleared.")
        raise typer.Exit(2)  # Argument error

    try:
        inventory.clear_state()
    except Exception as e:
        err_console.print(
            Panel.fit(
                f"[bold red]Error clearing inventory state:[/bold red] {e}",
                style="bold red",
            )
        )
        raise typer.Exit(1)  # Execution error
    else:
        console.print(
            Panel.fit(
                "Inventory state has been cleared. "
                "You will need to re-discover the inventory.",
                title="Cache Cleared",
            )
        )
