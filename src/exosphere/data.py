"""
Data Classes module

This module defines data classes used throughout the Exosphere
application.

These data classes are used to represent any kind of immutable,
structured data used in the application, usually for cross module
exchange or configuration purposes.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HostInfo:
    """
    Data class to hold platform information about a host.
    This includes the operating system, version, and package manager.
    """

    os: str
    version: str
    flavor: str
    package_manager: str


@dataclass(frozen=True)
class Update:
    """
    Data class to hold information about a software update.
    Includes the name of the software, the current version,
    new version, and optionally a source.
    """

    name: str
    current_version: str | None
    new_version: str
    security: bool = False
    source: str | None = None


@dataclass(frozen=True)
class ProviderInfo:
    """
    Data class to hold information about a package manager provider.
    Used by the CLI utilities and surrounding helper tools.
    """

    name: str
    class_name: str
    description: str
    reposync_requires_sudo: bool
    get_updates_requires_sudo: bool
    sudo_commands: list[str]
