"""
Reporting command module
"""

import json

import typer
from typing_extensions import Annotated

from exosphere.commands.utils import (
    console,
    err_console,
    get_hosts_or_error,
)

OUTPUT_FORMATS = ["json", "text"]

ROOT_HELP = """
Reporting Commands

Commands to generate reports about the current state of the inventory.
Allows exporting the state of the inventory to various formats, including
JSON for use in other tools or custom reporting.
"""

app = typer.Typer(
    help=ROOT_HELP,
    no_args_is_help=True,
)


@app.command()
def generate(
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format. Supported: json, text",
        ),
    ] = "text",
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file to write the report to. Defaults to stdout if not specified.",
            metavar="FILE",
        ),
    ] = None,
    tee: Annotated[
        bool,
        typer.Option(
            "--tee",
            help="Also print the report to stdout when writing to a file.",
            is_flag=True,
        ),
    ] = False,
    hosts: Annotated[
        list[str] | None,
        typer.Argument(
            help="List of hostnames or IP addresses to include in the report. All if not specified.",
            metavar="[HOST]...",
        ),
    ] = None,
) -> None:
    """
    Generate a report of the current inventory state.

    The report can be generated in various formats, including JSON for easy
    integration with other tools, or plain text for human readability.

    The report can also be filtered to include only specific hosts by
    providing their names as arguments. If no hosts are specified,
    the report will include all hosts in the inventory.

    Note: Undiscovered or unsupported hosts are excluded from the report.
    """

    # FIXME: This is kind of a bullshit proof of concept, fields, formats
    #        and logic are not final.

    if format not in OUTPUT_FORMATS:
        err_console.print(f"[red]Unsupported output format: {format}[/red]")
        err_console.print(f"Supported formats: {', '.join(OUTPUT_FORMATS)}")
        raise typer.Exit(code=1)

    selected_hosts = get_hosts_or_error(hosts)
    if selected_hosts is None:
        raise typer.Exit(code=1)

    # Filter out hosts that are unsupported or without a package manager
    # This excludes both undiscovered and unsupported hosts
    selected_hosts = [
        host for host in selected_hosts if host.supported and host.package_manager
    ]

    if not selected_hosts:
        err_console.print("[yellow]Host(s) found but none can be used![/yellow]")
        err_console.print(
            "Selected hosts must be supported and 'discover' must have been run."
        )
        raise typer.Exit(code=1)

    if format == "json":
        report_data = []
        for host in selected_hosts:
            host_data = {
                "name": host.name,
                "ip": host.ip,
                "port": host.port,
                "os": host.os,
                "flavor": host.flavor,
                "version": host.version,
                "online": host.online,
                "supported": host.supported,
                "package_manager": host.package_manager,
                "last_refresh": host.last_refresh.isoformat()
                if host.last_refresh
                else None,
                "updates": [
                    {
                        "name": update.name,
                        "current_version": update.current_version,
                        "new_version": update.new_version,
                        "security": update.security,
                        "source": update.source,
                    }
                    for update in host.updates
                ],
            }
            report_data.append(host_data)

        console.print(json.dumps(report_data, indent=2))
    elif format == "text":
        for host in selected_hosts:
            console.print(f"[bold]{host.name}[/bold] ({host.ip})")
            if host.package_manager:
                console.print(f"  Package Manager: {host.package_manager}")
            else:
                console.print("  Package Manager: [red]None[/red]")

            if not host.updates:
                console.print("  No updates available.")
            else:
                console.print("  Updates:")
                for update in host.updates:
                    security_suffix = "[red]*[/red]" if update.security else ""
                    console.print(
                        f"    - {update.name}: {update.current_version} -> {update.new_version} {security_suffix}"
                    )
            console.print()  # Blank line between hosts
    else:
        err_console.print(f"[red]Unsupported format: {format}[/red]")
        raise typer.Exit(code=1)
