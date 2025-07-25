"""
Sudo command module
"""

import fabric
import fabric.util
import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from exosphere import app_config, context
from exosphere.data import ProviderInfo
from exosphere.objects import Host
from exosphere.providers.factory import PkgManagerFactory
from exosphere.security import SudoPolicy, check_sudo_policy, has_sudo_flag

app = typer.Typer(
    help="Sudo Policy Management",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


def _get_inventory():
    """
    Get the inventory from context
    A convenience wrapper that bails if the inventory is not initialized
    """
    if context.inventory is None:
        err_console.print(
            "[red]Inventory is not initialized! Are you running this module directly?[/red]"
        )
        raise typer.Exit(1)

    return context.inventory


def _get_global_policy() -> SudoPolicy:
    """
    Get the default Sudo Policy from the app config.
    """
    return SudoPolicy(app_config["options"]["default_sudo_policy"])


def _get_provider_infos() -> dict[str, ProviderInfo]:
    """
    Get a dictionary of ProviderInfo objects for all available providers

    This includes the provider name, class name, and whether any of its methods
    require sudo privileges.
    """

    # Mapping of package manager names to their friendly descriptions.
    provider_mapping: dict[str, str] = {
        "apt": "Debian/Ubuntu Derivatives",
        "dnf": "Fedora/RHEL/CentOS Derivatives",
        "yum": "RHEL/CentOS 7 and earlier",
        "pkg": "FreeBSD",
    }

    results = {}

    for name, cls in PkgManagerFactory.get_registry().items():
        reposync_func = getattr(cls, "reposync", None)
        get_updates_func = getattr(cls, "get_updates", None)

        if (not reposync_func) or (not get_updates_func):
            err_console.print(
                f"[red]Provider {name} does not implement required methods! "
                "This is likely a bug.[/red]"
            )
            continue

        sudo_commands = getattr(cls, "SUDOERS_COMMANDS", [])

        info = ProviderInfo(
            name=name,
            class_name=cls.__qualname__,
            reposync_requires_sudo=has_sudo_flag(reposync_func),
            get_updates_requires_sudo=has_sudo_flag(get_updates_func),
            description=provider_mapping.get(name, name),
            sudo_commands=sudo_commands,
        )

        results[name] = info

    return results


def _format_sudo_status(requires_sudo: bool) -> str:
    """
    Format the sudo status for display in the table
    """
    return (
        "[red]Requires Sudo[/red]" if requires_sudo else "[green]No Privileges[/green]"
    )


def _format_can_run(
    can_run: bool,
) -> str:
    """
    Format the policy status for display in the table
    """
    return "[green]Yes[/green]" if can_run else "[red]No[/red]"


def _get_username(user: str | None, host: Host | None = None) -> str:
    """
    Resolve the username based on the provided user, host configuration,
    and application configuration defaults.
    """
    result = (
        user
        or (host.username if host else None)
        or app_config["options"]["default_username"]
        or fabric.util.get_local_user()
    )
    if result is None:
        err_console.print(
            "[red]No username could be selected. "
            "Please provide --user or ensure host configuration is correct.[/red]"
        )
        raise typer.Exit(1)

    # Validate username
    if not result.replace("-", "").replace("_", "").isalnum():
        err_console.print(
            f"[red]Invalid username '{result}'. "
            "Username must contain only alphanumeric characters, hyphens, and underscores.[/red]"
        )
        raise typer.Exit(1)

    return result


@app.command()
def policy():
    """
    Show the current global Sudo Policy.

    This command will display the current global Sudo Policy that is used
    to determine if a host can execute all of its Package Manager provider
    operations.
    """
    console.print(f"Global SudoPolicy: {_get_global_policy()}")


@app.command()
def check(
    host: str = typer.Argument(help="Host to check security policies for"),
):
    """
    Check the effective Sudo Policies for a given host.

    The command will take in consideration the current global Sudo Policy and the
    host-specific Sudo Policy (if defined) to determine if the host can execute
    all of its Package Manager provider operations.
    """

    # Collect data and sources
    global_policy = _get_global_policy()
    inventory = _get_inventory()
    target_host = inventory.get_host(host)

    if not target_host:
        err_console.print(f"[red]Host '{host}' not found in inventory![/red]")
        raise typer.Exit(1)

    # Collect sudo policies
    host_policy: SudoPolicy = target_host.sudo_policy
    policy_is_local = host_policy != global_policy

    # Collect package manager from host
    host_pkg_manager_name = target_host.package_manager
    if not host_pkg_manager_name:
        err_console.print(
            f"Host '{host}' does not have a package manager defined in the inventory."
            " Ensure discovery has been run on the host at least once!"
        )
        raise typer.Exit(1)

    # Get the package mananager class from the factory registry
    # We get the raw class to inspect, and do not need/want an instance
    host_pkg_manager = PkgManagerFactory.get_registry().get(host_pkg_manager_name)
    if not host_pkg_manager:
        err_console.print(
            f"[red]Host '{host}' has an unknown package manager: {host_pkg_manager_name}[/red]"
            " This is likely a bug and should be reported."
        )
        raise typer.Exit(1)

    # Gather sudo policy checks
    can_reposync = check_sudo_policy(host_pkg_manager.reposync, host_policy)
    can_get_updates = check_sudo_policy(host_pkg_manager.get_updates, host_policy)

    # Output data to console
    console.print(f"[bold]Sudo Policy for {host}[/bold]")
    console.print()

    # Prepare a Rich table to display the security policies
    # We're going to hide most of the table formatting so it just keeps
    # properties and values vertically aligned with each other.
    table = Table(
        "Property",
        "Value",
        show_header=False,
        show_lines=False,
        box=None,
        show_edge=False,
        show_footer=False,
    )

    table.add_row("Global Policy:", str(global_policy))

    if policy_is_local:
        table.add_row("Host Policy:", f"[cyan]{host_policy}[/cyan] (local)")
    else:
        table.add_row("Host Policy:", f"{host_policy} (global)")

    table.add_row("Package Manager:", host_pkg_manager_name)

    table.add_row("", "")  # Blank row for spacing

    table.add_row(
        "Can Sync Repositories:",
        _format_can_run(can_reposync),
    )
    table.add_row(
        "Can Refresh Updates:",
        _format_can_run(can_get_updates),
    )

    # Display results, with optional warnings
    console.print(table)
    console.print()

    if not can_reposync or not can_get_updates:
        err_console.print(
            "[yellow]Warning: One or more operations require sudo privileges "
            "that are not granted by the current policy.\n"
            "Some functionality may be limited.[/yellow]"
        )


@app.command()
def providers(
    name: Annotated[
        str | None, typer.Argument(help="Provider to display. All if not specified.")
    ] = None,
) -> None:
    """
    Show Sudo Policy requirements for available providers.

    Some providers require sudo privileges to execute certain operations.
    You can use this command to list them.
    """

    # prepare a nice rich Table for providers
    providers_table = Table(
        "Provider",
        "Platform",
        "Sync Repositories",
        "Refresh Updates",
        title="Providers Requirements",
    )

    provider_infos = _get_provider_infos()

    if name and name not in provider_infos:
        err_console.print(f"[red]No such provider: {name}")
        raise typer.Exit(1)

    target_providers = [provider_infos[name]] if name else list(provider_infos.values())

    for provider in target_providers:
        providers_table.add_row(
            provider.class_name,
            provider.description,
            _format_sudo_status(provider.reposync_requires_sudo),
            _format_sudo_status(provider.get_updates_requires_sudo),
        )

    console.print(providers_table)


@app.command()
def generate(
    host: Annotated[
        str | None,
        typer.Option(
            "--host",
            "-h",
            help="Generate sudoers snippet based on host configuration",
            rich_help_panel="Mandatory Options (mutually exclusive)",
            show_default=False,
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-p",
            help="Generate sudoers snippet for a specific provider",
            rich_help_panel="Mandatory Options (mutually exclusive)",
            show_default=False,
        ),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option(
            "--user",
            "-u",
            help="Override the username for the sudoers snippet",
            rich_help_panel="Optional",
            show_default="Host username OR default username OR Current user, in that order",
        ),
    ] = None,
) -> None:
    """
    Generate a sudoers configuration for passwordless operations.

    Creates snippet suitable for /etc/sudoers.d/* on target systems.

    Will use username from host configuration, global configuration,
    or current user if not specified.

    Outputs to stdout, can be redirected to a file.
    """
    if not host and not provider:
        err_console.print(
            "[red]You must specify either --host or --provider.[/red]\n"
            "Use --help for more information."
        )
        raise typer.Exit(1)

    if host and provider:
        err_console.print("[red]--host and --provider are mutually exclusive.[/red]")
        raise typer.Exit(1)

    inventory = _get_inventory()
    provider_infos = _get_provider_infos()

    target_user: str
    target_provider_name: str | None = None
    target_provider_info: ProviderInfo | None = None

    if host:
        target_host = inventory.get_host(host)
        if not target_host:
            err_console.print(f"[red]Host '{host}' not found in inventory![/red]")
            raise typer.Exit(1)

        target_provider_name = target_host.package_manager
        if not target_provider_name:
            err_console.print(
                f"Host '{host}' does not have a package manager "
                "defined in the inventory.\n"
                "Ensure discovery has been run on the host at least once, "
                "or specify [cyan]--provider[/cyan]."
            )
            raise typer.Exit(1)

        target_provider_info = provider_infos.get(target_provider_name)
        target_user = _get_username(
            user,
            target_host,
        )
    elif provider:
        target_provider_name = provider.lower()
        target_provider_info = provider_infos.get(target_provider_name)
        target_user = _get_username(user)
    else:
        assert False  # Validation failsafe

    if not target_provider_info:
        err_console.print(f"[red]No such provider: {target_provider_name}[/red]")
        raise typer.Exit(1)

    something_requires_sudo = (
        target_provider_info.reposync_requires_sudo
        or target_provider_info.get_updates_requires_sudo
    )

    # Abort with success if nothing requires sudo
    if not something_requires_sudo:
        err_console.print(
            f"Provider '{target_provider_name}' does not require any sudo commands.\n"
            "No additional configuration needed - all operations can run as-is."
        )
        raise typer.Exit(0)

    # Abort with failure if provider does not define any sudo commands
    if not target_provider_info.sudo_commands:
        err_console.print(
            f"[red]Provider '{target_provider_name}' does not define any sudo commands![/red]\n"
            "Can't generate: This is a bug in the provider and should be reported."
        )
        raise typer.Exit(1)

    # generate the sudoers config snippet with the commands from provider.SUDOERS_COMMANDS
    # and the target username
    sudoers_snippet = (
        f"# Generated for {target_provider_info.description}\n"
        f"Cmnd_Alias EXOSPHERE_CMDS = {', '.join(target_provider_info.sudo_commands or [])}\n"
        f"{target_user} ALL=(root) NOPASSWD: EXOSPHERE_CMDS"
    )

    # Do not use rich console for this output, as it is meant to be
    # potentially redirected to a file or copy pasted
    print(sudoers_snippet)
