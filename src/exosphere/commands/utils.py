"""
Common utilities for exosphere commands

Contains shared functionality and helpers for consistency across
exosphere commands, including inventory and host subcommands.

Contains mostly wrappers around inventory and host retrieval,
as well as display bits around task execution, errors and status.
"""

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

from exosphere import context
from exosphere.inventory import Inventory
from exosphere.objects import Host

# Constants for display formatting
STATUS_FORMATS = {
    "success": "[[bold green]OK[/bold green]]",
    "failure": "[[bold red]FAILED[/bold red]]",
}

console = Console()
err_console = Console(stderr=True)


def get_inventory() -> Inventory:
    """
    Get the inventory from context.
    A convenience wrapper that bails if the inventory is not initialized.

    Raises:
        typer.Exit: If inventory is not initialized

    Returns:
        Inventory: The active inventory instance
    """
    if context.inventory is None:
        typer.echo(
            "Inventory is not initialized, are you running this module directly?",
            err=True,
        )
        raise typer.Exit(code=1)

    return context.inventory


def get_host_or_error(name: str) -> Host | None:
    """
    Get a host by name from the inventory, printing an error if not found.
    Wraps inventory.get_host() to handle displaying errors on console.

    If the host is not found, pretty prints an error message on console.

    Args:
        name (str): The name of the host to retrieve

    Returns:
        Host | None: The host object if found, or None if not found
    """
    inventory = get_inventory()

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


def get_hosts_or_error(names: list[str] | None = None) -> list[Host] | None:
    """
    Get hosts from the inventory, filtering by names if provided.
    Will print an error message and return None if hosts are not found.

    Args:
        names: Optional list of host names to filter by. If None, returns all hosts.

    Returns:
        list[Host] | None: List of matching hosts, or None if no hosts found/matched
    """
    inventory = get_inventory()

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


def run_task_with_progress(
    inventory: Inventory,
    hosts: list[Host],
    task_name: str,
    task_description: str,
    display_hosts: bool = True,
    collect_errors: bool = True,
    immediate_error_display: bool = False,
    transient: bool = True,
    progress_args: tuple = (),
) -> list[tuple[str, Exception]]:
    """
    Run a task on selected hosts with progress display.
    This is a nice wrapper around inventory.run_task() that provides
    a progress bar and handles displaying updates and errors on console.

    Errors can be printed immediately above the progress bar on console.
    They can also be collected and returned as a list of tuples.

    These conditions are not mutually exclusive, so you can do both.

    Also exposes (by default) a status list in two columns as task runs,
    showing each host and whether the task succeeded or failed.

    If you need a custom progress bar layout, you can pass
    additional renderables in `progress_args` as a tuple, which this
    will unpack and pass to the Progress constructor.

    Args:
        inventory: The inventory instance
        hosts: List of Hosts to run the task on
        task_name: Name of the method to call on each host
        task_description: Description shown in progress bar
        display_hosts: Whether to show host status columns while running
        collect_errors: Whether to collect and return errors
        immediate_error_display: Whether to show errors immediately in progress context
        transient: Whether progress bar disappears after completion
        progress_args: List of renderables to compose the Progress layout

    Returns:
        List of (hostname, exception objects) tuples for any failed hosts
    """
    errors: list[tuple[str, Exception]] = []
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
                    errors.append((host.name, exc))

            if display_hosts:
                progress.console.print(
                    Columns([status_out, host_out], padding=(2, 1), equal=True)
                )

            progress.update(task, advance=1)

    return errors
