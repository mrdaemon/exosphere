"""
Reporting command module
"""

from enum import Enum
from pathlib import Path

import typer
from rich.json import JSON
from typing_extensions import Annotated

from exosphere.commands.utils import (
    console,
    err_console,
    get_hosts_or_error,
)
from exosphere.reporting import ReportRenderer


class OutputFormat(str, Enum):
    """Available output formats for reports"""

    text = "text"
    html = "html"
    markdown = "markdown"
    json = "json"


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
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format for the report",
        ),
    ] = OutputFormat.text,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write report to file (defaults to stdout)",
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    updates_only: Annotated[
        bool,
        typer.Option(
            "--updates-only",
            "-u",
            help="Only include hosts with available updates",
        ),
    ] = False,
    security_only: Annotated[
        bool,
        typer.Option(
            "--security-updates-only",
            "-s",
            help="Only report security updates",
        ),
    ] = False,
    tee: Annotated[
        bool,
        typer.Option(
            "--tee",
            help="Also print report to stdout when using --output",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress informational messages",
        ),
    ] = False,
    navigation: Annotated[
        bool,
        typer.Option(
            help="Include navigation section (html only)",
        ),
    ] = True,
    hosts: Annotated[
        list[str] | None,
        typer.Argument(
            help="One or more hosts to include (all if not specified)",
            metavar="[HOST]...",
        ),
    ] = None,
) -> None:
    """
    Generate a report of the current inventory state.

    The report can be generated in various formats, including html for
    for a pretty self-contained document, json for easy integration
    with other tools, or plain text for human readability.

    The report can also be filtered to include only specific hosts by
    providing their names as arguments. If no hosts are specified,
    the report will include all hosts in the inventory.

    Note: Undiscovered or unsupported hosts are excluded from the report.
    """

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
        if not selected_hosts and not quiet:
            err_console.print(
                "No hosts with available updates found, nothing to report."
            )
            raise typer.Exit(code=0)

    if security_only:
        selected_hosts = [host for host in selected_hosts if host.security_updates]
        if not selected_hosts and not quiet:
            err_console.print(
                "No hosts with security updates found, nothing to report."
            )
            raise typer.Exit(code=0)

    # Initialize the report renderer
    renderer = ReportRenderer()

    # Method dispatch table for rendering
    render_methods = {
        OutputFormat.json: renderer.render_json,
        OutputFormat.text: renderer.render_text,
        OutputFormat.markdown: renderer.render_markdown,
        OutputFormat.html: renderer.render_html,
    }

    render_method = render_methods.get(format)

    if render_method is None:
        # This should never happen due to early validation
        err_console.print(f"[red]Internal Error: Unsupported format: {format}[/red]")
        raise typer.Exit(code=1)

    content = render_method(
        selected_hosts, navigation=navigation, security_only=security_only
    )

    # Write file if necessary
    if output:
        try:
            output.write_text(content, encoding="utf-8")
        except Exception as e:
            err_console.print(f"[red]Failed to write to {output}: {e}[/red]")
            raise typer.Exit(code=1)

        if not tee and not quiet:
            err_console.print(
                f"Report saved to [green]{output}[/green] in [green]{format.value}[/green] format."
            )

    # Print to console if no output OR if tee is specified
    if not output or tee:
        try:
            if format == OutputFormat.json:
                console.print(JSON(content))
            else:
                console.print(content)
        except (BrokenPipeError, OSError):
            # Handle quirky Windows platform behavior with broken pipes
            # which powershell closes early a whole lot of the time.
            # Rich will write to stderr anyways to notify of the error,
            # this just prevents the humongous backtrace.
            pass
