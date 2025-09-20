"""
Reporting command module
"""

import json

import typer
from rich.json import JSON
from typing_extensions import Annotated

from exosphere.commands.utils import (
    console,
    err_console,
    get_hosts_or_error,
)
from exosphere.reporting import ReportRenderer

OUTPUT_FORMATS = ["json", "text", "markdown", "html"]

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
    updates_only: Annotated[
        bool,
        typer.Option(
            "--updates-only",
            "-u",
            help="Only include hosts with available updates in the report.",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format. Supported: json, text, markdown, html",
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
        ),
    ] = False,
    navigation: Annotated[
        bool,
        typer.Option(
            help="Include navigation section in report, if supported by format.",
        ),
    ] = True,
    hosts: Annotated[
        list[str] | None,
        typer.Argument(
            help="List of hosts to include in the report. All if not specified.",
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

    if updates_only:
        selected_hosts = [host for host in selected_hosts if host.updates]
        if not selected_hosts:
            err_console.print(
                "No hosts with available updates found, nothing to report."
            )
            raise typer.Exit(code=0)

    # Initialize the report renderer
    renderer = ReportRenderer()

    if format == "json":
        report_data = [host.to_dict() for host in selected_hosts]
        console.print(JSON(json.dumps(report_data, indent=2)))
    elif format == "text":
        output = renderer.render_text(selected_hosts, navigation=navigation)
        console.print(output)
    elif format == "markdown":
        output = renderer.render_markdown(selected_hosts, navigation=navigation)
        console.print(output)
    elif format == "html":
        output = renderer.render_html(selected_hosts, navigation=navigation)
        console.print(output)
    else:
        err_console.print(f"[red]Unsupported format: {format}[/red]")
        raise typer.Exit(code=1)
