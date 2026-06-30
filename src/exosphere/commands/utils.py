"""
Common utilities for exosphere commands

Contains shared functionality and helpers for consistency across
exosphere commands, including inventory and host subcommands.

Contains mostly wrappers around inventory and host retrieval,
as well as display bits around task execution, errors and status.
"""

import functools
import logging
import platform
import sys
from collections.abc import Callable
from typing import Annotated

from cyclopts import ArgumentCollection, Parameter
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

from exosphere import __version__, context
from exosphere.inventory import Inventory
from exosphere.objects import Host, HostOperation

# Shared spinner progress layout for indeterminate, single-step operations.
SPINNER_PROGRESS_ARGS = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TaskProgressColumn(),
    TimeElapsedColumn(),
)

# Constants for display formatting
STATUS_FORMATS = {
    "success": "[[bold green]OK[/bold green]]",
    "failure": "[[bold red]FAILED[/bold red]]",
    "skipped": "[[dim]SKIPPED[/dim]]",
}

console = Console()
err_console = Console(stderr=True)


def require_interactive[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """
    Restrict a command to interactive (REPL) use.

    Decorated command will raise SystemExit with code 2 if invoked from
    a the CLI in non-interactive mode, where it would make no sense.

    The criteria is typically commands that act on persistent state
    between commands, which does not occur outside the REPL.

    It must be applied *below* the ``@app.command`` decorator, so that
    cyclopts registers and introspects the wrapper::

        @app.command(show=False)
        @require_interactive
        def save() -> None: ...

    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if not context.interactive:
            err_console.print(
                "[yellow]This command is only available in Interactive Mode.[/yellow]"
            )
            raise SystemExit(2)  # Application error: wrong context
        return func(*args, **kwargs)

    return wrapper


def resolve_host(type_: type, tokens) -> Host:
    """
    Argument Converter for resolving a name to a :class:`Host`

    Raises ``ValueError`` for an unknown host.

    :param type_: The annotated target type (unused; always Host).
    :param tokens: The Cyclopts tokens parsed for this argument.
    :return: The resolved Host instance.
    """
    if context.inventory is None:
        raise ValueError("Inventory is not initialized.")

    name = tokens[0].value
    # Do not rely on get_inventory() here, to avoid raising
    # SystemExit in the middle of argument parsing.
    host = context.inventory.get_host(name)
    if host is None:
        raise ValueError(f"Host '{name}' not found in inventory.")

    return host


# Shared config for a Host token, consume one token and resolves it to
# to a Host object via the converter. Reused by both positionals and options.
# Do not nest this, or it will drop n_tokens.
HOST_PARAMETER = Parameter(n_tokens=1, converter=resolve_host, accepts_keys=False)

# Annotation for a positional Host argument that arrives already resolved.
HostArg = Annotated[Host, HOST_PARAMETER]


def arg_requires_arg(field: str, required: str) -> Callable[[ArgumentCollection], None]:
    """
    Build a group validator enforcing a one-way "requires" dependency.

    If the ``field`` parameter is supplied with a truthy value, then
    ``required`` must also be supplied; otherwise an input error is raised,
    naming both options by their primary CLI flag.

    Both parameters must belong to the same parameter group for the
    validator to see them. The message is derived from the arguments::

        Group("Sorting", validator=arg_requires_arg("reverse", "sort"))
        # --reverse without --sort -> "--reverse requires --sort."

    :param field: Parameter (field) name whose truthy value triggers the rule.
    :param required: Parameter (field) name that must then also be present.
    :return: A group validator callable suitable for a parameter group.
    """

    def _validator(arguments: ArgumentCollection) -> None:
        by_field = {arg.field_info.name: arg for arg in arguments}
        provided = {arg.field_info.name for arg in arguments.filter_by(value_set=True)}

        if field in provided and by_field[field].value and required not in provided:
            raise ValueError(
                f"{by_field[field].names[0]} requires {by_field[required].names[0]}."
            )

    return _validator


def get_version_string() -> str:
    """
    Return the formatted (Rich markup) Exosphere version string.
    """
    return (
        f"[bold cyan]Exosphere[/bold cyan] version "
        f"[bold green]{__version__}[/bold green]"
    )


def print_version() -> None:
    """
    Print the current version of Exosphere to stdout.
    Used by the 'version' command and '--version' option, for
    consistent output formatting.
    """
    console.print(get_version_string())


def print_environment() -> None:
    """
    Print the current environment (python version, venv, OS, etc) to stdout.
    Used by the 'version' command with verbose switch for consistent output
    formatting.
    """
    # Check if running in virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    venv_status = (
        "[bold green]Yes[/bold green]" if in_venv else "[bold red]No[/bold red]"
    )

    venv_path = f"[dim]{sys.prefix}[/dim]" if in_venv else "[dim]N/A[/dim]"

    # Create environment information table
    # We don't really show any edges, but use SIMPLE_HEAD
    # to delineate section ends for a cleaner look
    table = Table(
        show_header=False,
        show_edge=False,
        padding=(0, 1),
        box=box.SIMPLE_HEAD,
    )

    # Add columns -- the headers are not shown
    table.add_column("Category", style="bold blue")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    # Exosphere information
    table.add_row(
        "Exosphere", "Version", f"[bold]{__version__}[/bold]", end_section=True
    )

    # Python information
    table.add_row(
        "Python",
        "Version",
        f"[bold]{platform.python_version()} ({platform.python_implementation()})[/bold]",
    )
    table.add_row("", "Bin", sys.executable)

    if in_venv:
        table.add_row("", "Venv", venv_status)
        table.add_row("", "Venv Path", venv_path, end_section=True)
    else:
        table.add_row("", "Venv", venv_status, end_section=True)

    # System information
    table.add_row("System", "OS", f"{platform.system()} {platform.release()}")
    table.add_row("", "Version", platform.version())
    table.add_row("", "Machine", platform.machine())

    processor = platform.processor()
    if processor:
        table.add_row("", "CPU", processor)

    # Surround table with blank lines for implicit spacing
    console.print()
    console.print(table)
    console.print()


def get_inventory() -> Inventory:
    """
    Get the inventory from context.
    A convenience wrapper that bails if the inventory is not initialized.

    :raises SystemExit: code 2 (application error) if inventory is not initialized
    :return: The active inventory instance
    """
    if context.inventory is None:
        err_console.print(
            "Inventory is not initialized, are you running this module directly?"
        )
        raise SystemExit(2)  # Application error

    return context.inventory


def get_hosts_or_all(
    hosts: tuple[Host, ...], supported_only: bool = False
) -> list[Host] | None:
    """
    Obtain the given resolved hosts, or all inventory hosts if none were given.

    Helper intended exclusively for commands that take a variadic
    ``*names: HostArg`` argument, and hinges on unknown hosts being
    already rejected by the CLI Converter.

    Meant to handle the common "no hosts specified -> all hosts" default,
    the empty inventory scenario, and the optional supported only filter.

    :param hosts: Resolved hosts from a variadic host argument (empty for all).
    :param supported_only: Return only supported hosts, with warning
    :return: The resolved Host objects to operate on, or None.
    """
    explicit = bool(hosts)

    if hosts:
        selected = list(hosts)
    else:
        selected = list(get_inventory().hosts)
        if not selected:
            err_console.print(Panel.fit("No hosts found in inventory.", title="Error"))
            return None

    if supported_only:
        supported = [h for h in selected if h.supported and h.package_manager]
        unsupported = set(selected) - set(supported)

        if not supported:
            where = "specified list" if explicit else "inventory"
            err_console.print(
                Panel.fit(
                    f"No supported hosts found in {where}. "
                    "Ensure 'discover' has been run.",
                    title="Error",
                )
            )
            return None

        # Warn about skipped hosts only when the user named specific ones.
        if unsupported and explicit:
            err_console.print(
                Panel.fit(
                    "Unsupported hosts will be skipped: "
                    f"{', '.join(h.name for h in unsupported)}",
                    title="Warning",
                    style="yellow",
                )
            )

        return supported

    return selected


def run_task_with_progress(
    inventory: Inventory,
    hosts: list[Host],
    operation: HostOperation,
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

    :param inventory: The inventory instance
    :param hosts: List of Hosts to run the task on
    :param operation: The :class:`HostOperation` to run on each host
    :param task_description: Description shown in progress bar
    :param display_hosts: Whether to show host status columns while
        running
    :param collect_errors: Whether to collect and return errors
    :param immediate_error_display: Whether to show errors immediately in
        progress context
    :param transient: Whether progress bar disappears after completion
    :param progress_args: List of renderables to compose the Progress
        layout
    :return: List of (hostname, exception objects) tuples for any failed
        hosts
    """
    errors: list[tuple[str, Exception]] = []

    # Pre-filter hosts based on whether or not they can run the operation
    if operation.requires_supported:
        skipped = [host for host in hosts if not host.supported]
        hosts = [host for host in hosts if host.supported]
    else:
        skipped = []

    with Progress(transient=transient, *progress_args) as progress:
        task = progress.add_task(task_description, total=len(hosts))

        # Surface skipped hosts up front, if any. It is easier to do
        # this before starting so it doesn't get tangled with other
        # messages and the behavior of immediate errors.
        if display_hosts and skipped:
            for host in skipped:
                progress.console.print(
                    Columns(
                        [STATUS_FORMATS["skipped"], f"[bold]{host.name}[/bold]"],
                        padding=(2, 1),
                        equal=True,
                    )
                )

        for host, _, exc in inventory.run_task(operation, hosts=hosts):
            status_out = STATUS_FORMATS["failure"] if exc else STATUS_FORMATS["success"]
            host_out = f"[bold]{host.name}[/bold]"

            if exc:
                if immediate_error_display:
                    progress.console.print(
                        f"{operation.label}: [red]{str(exc)}[/red]",
                    )

                if collect_errors:
                    errors.append((host.name, exc))

            if display_hosts:
                progress.console.print(
                    Columns([status_out, host_out], padding=(2, 1), equal=True)
                )

            progress.update(task, advance=1)

    return errors


def save_inventory_state() -> None:
    """
    Write the current inventory state to the cache file.

    This is the shared CLI implementation, with indeterminate progress,
    shared between commands and hooks that need to call
    inventory.save_state().

    :raises SystemExit: code 2 (application error) if persistence fails.
    """
    logger = logging.getLogger(__name__)
    logger.debug("Starting inventory save operation")

    inventory = get_inventory()

    with Progress(*SPINNER_PROGRESS_ARGS, transient=True) as progress:
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
            raise SystemExit(2)  # Application error

    logger.debug("Inventory save operation completed")
