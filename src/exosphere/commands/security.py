from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from exosphere.auth import has_sudo_flag
from exosphere.providers.factory import PkgManagerFactory

app = typer.Typer(
    help="Security Policy related commands",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


@dataclass
class ProviderInfo:
    name: str
    class_name: str
    reposync_requires_sudo: bool
    get_updates_requires_sudo: bool


def _get_provider_infos() -> dict[str, ProviderInfo]:
    """
    Get a dictionary of ProviderInfo objects for all available providers

    This includes the provider name, class name, and whether any of its methods
    require sudo privileges.
    """

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

        info = ProviderInfo(
            name=name,
            class_name=cls.__qualname__,
            reposync_requires_sudo=has_sudo_flag(reposync_func),
            get_updates_requires_sudo=has_sudo_flag(get_updates_func),
        )

        results[name] = info

    return results


def _format_sudo_status(requires_sudo: bool) -> str:
    """
    Format the sudo status for display in the table
    """
    return "[red]Requires Sudo[/red]" if requires_sudo else "[green]OK[/green]"


@app.command()
def check(
    host: str = typer.Argument(..., help="Host to check security policies for"),
):
    """
    Check the security policies for a given host.
    """
    console.print(f"Checking security policies for host: {host}", style="bold green")
    console.print(
        "This is where I would shit whether or not stuff would run for the host"
    )


@app.command()
def providers(
    name: Annotated[
        str | None, typer.Argument(help="Provider to display. All if not specified.")
    ] = None,
) -> None:
    """
    List Package Manager Providers in Exosphere and their Security Requirements

    Some providers require sudo provileges to execute certain operations. You can use
    this command to list them.
    """

    # prepare a nice rich Table for providers
    providers_table = Table(
        "Provider",
        "Class",
        "Refresh Catalog",
        "Refresh Updates",
        title="Available Providers",
    )

    provider_infos = _get_provider_infos()

    if name and name not in provider_infos:
        err_console.print(f"[red]No such provider: {name}")
        return

    target_providers = [provider_infos[name]] if name else list(provider_infos.values())

    for provider in target_providers:
        providers_table.add_row(
            provider.name,
            provider.class_name,
            _format_sudo_status(provider.reposync_requires_sudo),
            _format_sudo_status(provider.get_updates_requires_sudo),
        )

    console.print(providers_table)
