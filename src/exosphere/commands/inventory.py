"""
Inventory command module
"""

import logging
import sys
from typing import Annotated

from cyclopts import App, Group, Parameter, validators
from rich import box
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Confirm
from rich.table import Table

from exosphere import app_config
from exosphere.commands.utils import (
    SPINNER_PROGRESS_ARGS,
    HostArg,
    arg_requires_arg,
    console,
    err_console,
    get_hosts_or_all,
    get_inventory,
    require_interactive,
    run_task_with_progress,
    save_inventory_state,
)
from exosphere.inventory import FilterMode, Inventory, SortField
from exosphere.objects import HostOperation

# Constants for display
ERROR_STYLE = {
    "style": "bold red",
    "title_align": "left",
}

SORT_COLUMNS = ", ".join(field.value for field in SortField)

ROOT_HELP = """
Inventory and Bulk Management Commands

Commands to bulk query, discover and refresh hosts in the inventory.
Most commands accept an optional list of host names to operate on.
"""

app = App(name="inventory", help=ROOT_HELP, help_flags=["--help"])


@app.command
def discover(*names: HostArg) -> int:
    """
    Gather platform information for hosts

    On a fresh inventory start, this needs to be done at least once
    before operations can be performed on the hosts. It can also be
    used to refresh this information if it has changed, or if a new
    provider has been added to Exosphere.

    The discover operation will connect to the specified host(s)
    and gather their current state, including Operating System, flavor,
    version and pick a Package Manager implementation for further
    operations.

    Parameters
    ----------
    names
        Host(s) to discover, all if not specified
    """
    logger = logging.getLogger(__name__)
    logger.info("Gathering platform information for hosts")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_all(names)
    if hosts is None:
        return 1  # Input error: no hosts to operate on

    errors = run_task_with_progress(
        inventory=inventory,
        hosts=hosts,
        operation=HostOperation.DISCOVER,
        task_description="Gathering platform information",
        display_hosts=True,
        collect_errors=True,
        immediate_error_display=False,
    )

    errors_table = Table(
        "Host", "Error", show_header=False, show_lines=False, box=box.SIMPLE_HEAD
    )

    if errors:
        console.print()
        console.print("The following hosts could not be discovered due to errors:")
        for host, error in errors:
            errors_table.add_row(host, f"[bold red]{error}[/bold red]")

        console.print(errors_table)

    if app_config["options"]["cache_autosave"]:
        save_inventory_state()

    return 2 if errors else 0  # Application error if any host failed


@app.command(synonym="sync")
def refresh(
    *names: HostArg,
    discover: Annotated[
        bool, Parameter(name=["--discover", "-d"], negative="")
    ] = False,
    sync: Annotated[bool, Parameter(name=["--sync", "-s"], negative="")] = False,
    verbose: Annotated[bool, Parameter(name=["--verbose", "-v"], negative="")] = False,
) -> int:
    """
    Refresh the update data for all hosts

    Connects to hosts in the inventory and retrieves pending package
    updates.

    If `--discover` is specified, the platform information (Operating
    System flavor, version, package manager) will also be refreshed.
    Also refreshes the online status in the process.

    If `--sync` is specified, the package repositories will also be synced.

    Syncing the package repositories involves invoking whatever mechanism
    the package manager uses to achieve this, and can be a very expensive
    operation, which may take a long time, especially on large inventories
    with a handful of slow hosts.

    By default, only the progress bar is shown during the operation.
    If `--verbose` is specified, the name and completion status of each host
    will be shown in real time.

    Parameters
    ----------
    names
        Host(s) to refresh, all if not specified
    discover
        Also refresh platform information
    sync
        Sync the package repositories as well as updates
    verbose
        Show verbose output during operations
    """
    logger = logging.getLogger(__name__)
    logger.info("Refreshing inventory data")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_all(names)
    if hosts is None:
        return 1  # Input error: no hosts to operate on

    # Start with discovery, if requested.
    # Displays a simple spinner with no ETA, and no progress bar.
    if discover:
        console.print("[dim]Discovery:[/dim]") if verbose else None
        run_task_with_progress(
            inventory=inventory,
            hosts=hosts,
            operation=HostOperation.DISCOVER,
            task_description="Gathering platform information",
            display_hosts=verbose,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
        )
        console.print() if verbose else None

    # Unsupported hosts can't sync or refresh, partition them off
    # This is handed to the task runner which will handle display
    runnable = [host for host in hosts if host.supported]
    skipped = [host for host in hosts if not host.supported]

    # If sync is requested, we will run the sync_repos task
    # Same as discovery, simple spinner
    if sync:
        console.print("[dim]Repository Sync:[/dim]") if verbose else None
        run_task_with_progress(
            inventory=inventory,
            hosts=runnable,
            operation=HostOperation.SYNC,
            task_description="Syncing package repositories",
            display_hosts=verbose,
            collect_errors=False,
            immediate_error_display=True,
            progress_args=SPINNER_PROGRESS_ARGS,
            skipped=skipped,
        )
        console.print() if verbose else None

    # Finally, refresh the updates for all hosts
    # We want this one to display the progress bar and summarize errors.
    console.print("[dim]Updates Refresh:[/dim]") if verbose else None
    errors = run_task_with_progress(
        inventory=inventory,
        hosts=runnable,
        operation=HostOperation.REFRESH,
        task_description="Refreshing package updates",
        display_hosts=verbose,
        collect_errors=True,
        immediate_error_display=False,
        skipped=skipped,
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
        save_inventory_state()

    if errors:
        console.print()
        for host, error in errors:
            errors_table.add_row(host, f"[bold red]{error}[/bold red]")

        console.print(errors_table)

        return 2  # Application error

    return 0


@app.command
def ping(*names: HostArg) -> int:
    """
    Ping all hosts in the inventory

    Attempts to connect to all hosts in the inventory.
    On failure, the affected host will be marked as offline.

    You can use this command to quickly check whether or not
    hosts are reachable and online.

    Invoke this to update the online status of hosts if
    any have gone offline and exosphere refuses to run
    an operation on them.

    Parameters
    ----------
    names
        Host(s) to ping, all if not specified
    """
    logger = logging.getLogger(__name__)
    logger.info("Pinging all hosts in the inventory")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_all(names)
    if hosts is None:
        logger.error("No host(s) found, aborting")
        return 1  # Input error: no hosts to operate on

    with Progress(
        transient=True,
    ) as progress:
        error_count = 0
        task = progress.add_task("Pinging hosts", total=len(hosts))
        for host, status, exc in inventory.run_task(HostOperation.PING, hosts=hosts):
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
        save_inventory_state()

    if error_count > 0:
        return 2  # Application error

    return 0


STATUS_FILTER_GROUP = Group(
    "Filtering Options", validator=validators.mutually_exclusive
)
STATUS_SORT_GROUP = Group(
    "Sorting Options", validator=arg_requires_arg("reverse", "sort")
)


@app.command(synonym=["list", "show"])
def status(
    *names: HostArg,
    updates_only: Annotated[
        bool,
        Parameter(
            name=["--updates-only", "-u"], negative="", group=STATUS_FILTER_GROUP
        ),
    ] = False,
    security_only: Annotated[
        bool,
        Parameter(
            name=["--security-only", "-s"],
            negative="",
            group=STATUS_FILTER_GROUP,
        ),
    ] = False,
    sort: Annotated[
        SortField | None,
        Parameter(
            name=["--sort", "-o"],
            group=STATUS_SORT_GROUP,
        ),
    ] = None,
    reverse: Annotated[
        bool,
        Parameter(
            name=["--reverse", "-r"],
            negative="",
            group=STATUS_SORT_GROUP,
        ),
    ] = False,
    full: Annotated[bool, Parameter(name=["--full", "-f"], negative="")] = False,
) -> int:
    """
    Show hosts and their status

    Display a nice table with the current state of all the hosts
    in the inventory, including their package update counts, their
    online status and whether or not the data is stale.

    Output can be filtered to show only hosts with pending updates
    (`--updates-only`) or only those with pending security updates
    (`--security-only`). These two filters are mutually exclusive.

    Output can also be sorted by any column with `--sort`, optionally
    reversed with `--reverse`. Sorting by 'version' groups hosts by
    flavor first, since versions are not comparable across flavors.

    When sorting by any column other than name, hosts with unknown
    or unsupported values for that column will be grouped together at the
    end.

    Use `--full` to include extra columns, such as the host description.

    No matches when filtering will exit with code 3.

    Parameters
    ----------
    names
        Host(s) to show status for, all if not specified
    updates_only
        Show only hosts with pending updates
    security_only
        Show only hosts with pending security updates
    sort
        Sort the table by the given column
    reverse
        Reverse the sort order (requires `--sort`)
    full
        Show additional columns, including host descriptions
    """
    logger = logging.getLogger(__name__)
    logger.info("Showing status of all hosts")

    inventory: Inventory = get_inventory()

    hosts = get_hosts_or_all(names)
    if hosts is None:
        return 1  # Input error: no hosts to operate on

    # Map the active filter flag to a FilterMode and table title.
    # --updates-only and --security-only are mutually exclusive (enforced by
    # the Filtering Options group validator), so at most one is set here.
    match (updates_only, security_only):
        case (False, True):
            filter_mode = FilterMode.SECURITY_ONLY
            table_suffix = "(security updates only)"
        case (True, False):
            filter_mode = FilterMode.UPDATES_ONLY
            table_suffix = "(updates only)"
        case _:
            filter_mode = FilterMode.NONE
            table_suffix = "Overview"

    hosts = inventory.filter_hosts(filter_mode, hosts=hosts)

    if not hosts:
        console.print(Panel.fit("No hosts matching requested criteria."))
        return 3  # No matches for filtering

    # The validator prevents --reverse without --sort
    if sort is not None:
        hosts = inventory.sort_hosts(sort, hosts=hosts, reverse=reverse)

    # Iterates through all hosts in the inventory and render a nice
    # Rich table with their properties and status. The sortable column
    # headers are driven by the SortField enum so they stay in sync with
    # sorting; --full appends extra, display-only columns after them.
    columns = [field.label for field in SortField]
    if full:
        columns.append("Description")

    table = Table(
        *columns,
        title=f"Host Status {table_suffix}",
        caption="Legend: * stale data, ! pending reboot",
        caption_justify="right",
    )

    for host in hosts:
        # Prepare some rendering data for suffixes and placeholders
        stale_suffix = " [dim]*[/dim]" if host.is_stale else ""
        reboot_suffix = " [red]![/red]" if host.needs_reboot else ""
        undiscovered_status = "[dim](undiscovered)[/dim]"
        unsupported_status = "[dim](unsupported)[/dim]"
        empty_placeholder = "[dim]—[/dim]"

        # Prepare table row data
        if host.supported and host.os is not None:
            updates = f"{len(host.updates)}{stale_suffix}"

            sec_count = len(host.security_updates) if host.security_updates else 0
            security_updates = (
                f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
            ) + stale_suffix
        else:
            # Do not show update counts for unsupported or undiscovered
            # hosts - they do not contribute meaningful data.
            updates = empty_placeholder
            security_updates = empty_placeholder

        online_status = (
            "[bold green]Online[/bold green]" if host.online else "[red]Offline[/red]"
        ) + reboot_suffix

        # Helper function to get platform info with appropriate
        # handling for unsupported and undiscovered hosts
        def get_platform_info(value):
            if value:
                return value
            elif not host.supported:
                return unsupported_status
            else:
                return undiscovered_status

        # Construct table row for host
        row = [
            host.name,
            get_platform_info(host.os),
            get_platform_info(host.flavor),
            get_platform_info(host.version),
            updates,
            security_updates,
            online_status,
        ]
        if full:
            row.append(host.description or empty_placeholder)

        table.add_row(*row)

    console.print(table)

    return 0


@app.command(show=False)  # Interactive-only command (hidden)
@require_interactive
def save() -> None:
    """
    Save the current inventory state to disk

    Manually save the current state of the inventory to disk using the
    configured cache file.

    The data is compressed using LZMA.

    If options.cache_autosave is enabled, this will be automatically
    invoked after every discovery or refresh operation.

    Since this is enabled by default, you will rarely need to invoke this
    manually.

    This command is only available in interactive mode, as the inventory
    state is not persisted between separate CLI invocations when autosave
    is disabled.
    """
    save_inventory_state()


@app.command(synonym="reset")
def clear(
    *,
    force: Annotated[bool, Parameter(name=["--force", "-f"], negative="")] = False,
) -> int:
    """
    Clear the inventory state and cache file

    This will empty the inventory cache file and re-initialize
    all hosts from scratch.

    This is useful if you want to reset the inventory state, or
    have difficulties with stale data that cannot be resolved.

    Note that this will remove all cached host data, so you will
    need to re-discover the entire inventory after this operation.

    Parameters
    ----------
    force
        Do not prompt for confirmation
    """
    inventory: Inventory = get_inventory()

    if not force and not sys.stdin.isatty():
        err_console.print(
            "Not a TTY - cannot prompt for confirmation. "
            "Use --force to bypass confirmation in scripted contexts."
        )
        return 1  # Input error: cannot prompt

    if not force and not Confirm.ask("Clear inventory state?", default=False):
        console.print("Inventory state has [bold]not[/bold] been cleared.")
        return 1  # Input error: not confirmed

    try:
        inventory.clear_state()
    except Exception as e:
        err_console.print(
            Panel.fit(
                f"[bold red]Error clearing inventory state:[/bold red] {e}",
                style="bold red",
            )
        )
        return 2  # Application error
    else:
        console.print(
            Panel.fit(
                "Inventory state has been cleared. "
                "You will need to re-discover the inventory.",
                title="Cache Cleared",
            )
        )

    return 0
