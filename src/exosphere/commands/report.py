"""
Reporting command module
"""

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators
from rich.json import JSON

from exosphere.commands.utils import (
    HostArg,
    console,
    err_console,
    get_hosts_or_all,
)
from exosphere.reporting import OutputFormat, ReportRenderer, ReportScope, ReportType

ROOT_HELP = """
Reporting Commands

Commands to generate reports about the current state of the inventory.
Allows exporting the state of the inventory to various formats, including
JSON for use in other tools or custom reporting.
"""

app = App(
    name="report",
    help=ROOT_HELP,
    help_flags=["--help"],
    console=console,
    error_console=err_console,
)


@app.command
def generate(
    *hosts: HostArg,
    format: Annotated[
        OutputFormat, Parameter(name=["--format", "-f"])
    ] = OutputFormat.text,
    output: Annotated[
        Path | None,
        Parameter(name=["--output", "-o"], validator=validators.Path(dir_okay=False)),
    ] = None,
    updates_only: Annotated[
        bool, Parameter(name=["--updates-only", "-u"], negative="")
    ] = False,
    security_only: Annotated[
        bool, Parameter(name=["--security-updates-only", "-s"], negative="")
    ] = False,
    tee: Annotated[bool, Parameter(name=["--tee"], negative="")] = False,
    quiet: Annotated[bool, Parameter(name=["--quiet", "-q"], negative="")] = False,
    navigation: bool = True,
) -> int:
    """
    Generate a report of the current inventory state.

    The report can be generated in various formats, including html for
    for a pretty self-contained document, json for easy integration
    with other tools, or plain text for human readability.

    The report can also be filtered to include only specific hosts by
    providing their names as arguments. If no hosts are specified,
    the report will include all hosts in the inventory.

    Note: Undiscovered or unsupported hosts are excluded from the report.

    Parameters
    ----------
    hosts
        One or more hosts to include (all if not specified)
    format
        Output format for the report
    output
        Write report to file (defaults to stdout)
    updates_only
        Only include hosts with available updates
    security_only
        Only report security updates
    tee
        Also print report to stdout when using --output
    quiet
        Suppress informational messages
    navigation
        Include navigation section (html only)
    """
    # Default state is a full report of all hosts
    report_type = ReportType.full
    report_scope = ReportScope.complete

    selected_hosts = get_hosts_or_all(hosts, supported_only=True)
    if selected_hosts is None:
        return 1  # Input error: no hosts to report on

    # Record count of hosts involved in the report before
    # any kind of filtering. This is used by the report to
    # display Total/Selected hosts even when filtering by
    # updates or security updates.
    total_hosts = len(selected_hosts)

    if hosts:
        report_scope = ReportScope.filtered

    if updates_only:
        selected_hosts = [host for host in selected_hosts if host.updates]
        if not selected_hosts and not quiet:
            err_console.print(
                "No hosts with available updates found, nothing to report."
            )
            return 0  # Success: nothing to report

        report_type = ReportType.updates_only

    if security_only:
        selected_hosts = [host for host in selected_hosts if host.security_updates]
        if not selected_hosts and not quiet:
            err_console.print(
                "No hosts with security updates found, nothing to report."
            )
            return 0  # Success: nothing to report

        report_type = ReportType.security_only

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
        err_console.print("This is a bug and should be reported.")
        return 2  # Application error

    content = render_method(
        selected_hosts,
        hosts_count=total_hosts,
        report_type=report_type,
        report_scope=report_scope,
        navigation=navigation,
    )

    # Write file if necessary
    if output:
        try:
            output.write_text(content, encoding="utf-8")
        except Exception as e:
            err_console.print(f"[red]Failed to write to {output}: {e}[/red]")
            return 2  # Application error

        if not tee and not quiet:
            err_console.print(
                f"Report of type [green]{report_type.value}, {report_scope.value}[/green] "
                f"saved to [green]{output}[/green] in [green]{format.value}[/green] format."
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

    return 0
