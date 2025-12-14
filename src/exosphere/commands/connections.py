"""
Connections command module
"""

import time

import typer
from rich.table import Table
from typing_extensions import Annotated

from exosphere import app_config
from exosphere.commands.utils import (
    console,
    err_console,
    get_hosts_or_error,
)

ROOT_HELP = """
Connections State Commands

Commands to inspect the state of SSH connections to inventory hosts.
"""

app = typer.Typer(
    help=ROOT_HELP,
    no_args_is_help=True,
)


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return (
            f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
        )
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"


@app.command()
def show(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Hosts to show connection state for. If omitted, shows all hosts.",
            metavar="[HOSTS]...",
        ),
    ] = None,
) -> None:
    """
    Show SSH connection state for inventory hosts.
    """

    if not app_config["options"]["ssh_pipelining"]:
        err_console.print("[yellow]SSH Pipelining is currently disabled.[/yellow]")
        err_console.print("No persistent connections to hosts are maintained.")
        raise typer.Exit(1)

    pipelining_max_age = app_config["options"]["ssh_pipelining_lifetime"]
    pipelining_interval = app_config["options"]["ssh_pipelining_reap_interval"]

    hosts = get_hosts_or_error(names)
    if hosts is None:
        raise typer.Exit(code=2)  # Argument error

    table = Table(
        "Host",
        "IP",
        "Port",
        "Idle",
        "State",
        title="SSH Connection States",
        caption=f"Idle connections older than {pipelining_max_age}s are closed every {pipelining_interval}s",
        caption_justify="right",
    )

    for host in hosts:
        host_name = host.name
        host_ip = host.ip
        host_port = host.port

        if host.connection_last_used is not None:
            idle_seconds = round(time.time() - host.connection_last_used)
            host_idle = _format_duration(idle_seconds)

            # Expiring connections should be marked as such
            # The reaper adds some splay time.
            if idle_seconds >= pipelining_max_age:
                state = "[yellow]Expiring[/yellow]"
            else:
                state = "[green]Connected[/green]"
        else:
            host_idle = "[dim]—[/dim]"
            idle_seconds = None
            state = "[dim]Inactive[/dim]"

        table.add_row(
            str(host_name),
            str(host_ip),
            str(host_port),
            host_idle,
            state,
        )

    console.print(table)


@app.command()
def close(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            help="Hosts to close connections for. If omitted, close all connections.",
            metavar="[HOSTS]...",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed output of closed connections.",
        ),
    ] = False,
) -> None:
    """
    Close SSH connections explicitly

    Close SSH connections to specified hosts, or all hosts if none are specified.
    Only useful when SSH Pipelining is enabled.
    """

    if not app_config["options"]["ssh_pipelining"]:
        err_console.print("[yellow]SSH Pipelining is currently disabled.[/yellow]")
        err_console.print("No persistent connections to hosts are maintained.")
        raise typer.Exit(1)

    hosts = get_hosts_or_error(names)
    if hosts is None:
        raise typer.Exit(code=2)  # Argument error

    closed_count = 0
    inactive_count = 0

    for host in hosts:
        if host.connection_last_used is None:
            inactive_count += 1
            continue

        host.close()
        closed_count += 1

        if verbose:
            console.print(f"  [bold]{host.name}[/bold]: Connection closed.")

    if closed_count > 0:
        console.print(f"Closed [bold]{closed_count}[/bold] active connection(s).")

    if verbose and inactive_count > 0:
        console.print(
            f"[dim]Skipped {inactive_count} host(s) with no active connections.[/dim]"
        )
