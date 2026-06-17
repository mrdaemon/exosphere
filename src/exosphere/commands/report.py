"""
Reporting command module
"""

from pathlib import Path
from typing import Annotated

from cyclopts import App, ArgumentCollection, Group, Parameter, validators
from rich.json import JSON

from exosphere.commands.utils import (
    HostArg,
    arg_requires_arg,
    console,
    err_console,
    get_hosts_or_all,
    get_inventory,
)
from exosphere.inventory import FilterMode
from exosphere.reporting import OutputFormat, ReportRenderer, ReportScope, ReportType

ROOT_HELP = """
Reporting Commands

Commands to generate reports about the current state of the inventory.
Allows exporting the state of the inventory to various formats, including
JSON for use in other tools or custom reporting.
"""

app = App(name="report", help=ROOT_HELP, help_flags=["--help"])


def _validate_navigation_option(arguments: ArgumentCollection) -> None:
    """
    Group validator: ``--no-navigation`` only applies to HTML output.

    The navigation section only exists in the HTML report, so disabling it
    for any other format is meaningless.
    """
    by_field = {arg.field_info.name: arg for arg in arguments}
    set_fields = {arg.field_info.name for arg in arguments.filter_by(value_set=True)}

    no_navigation = "navigation" in set_fields and by_field["navigation"].value is False
    if not no_navigation:
        return

    is_html = "format" in set_fields and by_field["format"].value == OutputFormat.html
    if not is_html:
        raise ValueError("--no-navigation only applies to --format html.")


FILTER_GROUP = Group("Filtering Options", validator=validators.mutually_exclusive)
OUTPUT_GROUP = Group(
    "Output Options",
    validator=(arg_requires_arg("tee", "output"), _validate_navigation_option),
)


@app.command
def generate(
    *hosts: HostArg,
    format: Annotated[
        OutputFormat, Parameter(name=["--format", "-f"], group=OUTPUT_GROUP)
    ] = OutputFormat.text,
    output: Annotated[
        Path | None,
        Parameter(
            name=["--output", "-o"],
            validator=validators.Path(dir_okay=False),
            group=OUTPUT_GROUP,
        ),
    ] = None,
    updates_only: Annotated[
        bool,
        Parameter(name=["--updates-only", "-u"], negative="", group=FILTER_GROUP),
    ] = False,
    security_only: Annotated[
        bool,
        Parameter(
            name=["--security-updates-only", "-s"], negative="", group=FILTER_GROUP
        ),
    ] = False,
    tee: Annotated[
        bool, Parameter(name=["--tee"], negative="", group=OUTPUT_GROUP)
    ] = False,
    quiet: Annotated[
        bool, Parameter(name=["--quiet", "-q"], negative="", group=OUTPUT_GROUP)
    ] = False,
    navigation: Annotated[bool, Parameter(group=OUTPUT_GROUP)] = True,
) -> int:
    """
    Generate a report of the current inventory state.

    The report can be generated in various formats, including html for
    for a pretty self-contained document, json for easy integration
    with other tools, or plain text for human readability.

    The report can also be filtered to include only specific hosts by
    providing their names as arguments. If no hosts are specified,
    the report will include all hosts in the inventory.

    It can further be narrowed to hosts with pending updates
    (`--updates-only`) or pending security updates
    (`--security-updates-only`), which are mutually exclusive.

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
        Also print report to stdout (requires `--output`)
    quiet
        Suppress informational messages
    navigation
        Include navigation section (html only)
    """
    # Default state is a full report of all hosts
    report_type = ReportType.full
    report_scope = ReportScope.complete

    inventory = get_inventory()

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
        selected_hosts = inventory.filter_hosts(
            FilterMode.UPDATES_ONLY, hosts=selected_hosts
        )
        if not selected_hosts and not quiet:
            err_console.print(
                "No hosts with available updates found, nothing to report."
            )
            return 0  # Success: nothing to report

        report_type = ReportType.updates_only

    if security_only:
        selected_hosts = inventory.filter_hosts(
            FilterMode.SECURITY_ONLY, hosts=selected_hosts
        )
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
