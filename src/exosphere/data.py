"""
Data Classes module

This module defines data classes used throughout the Exosphere
application.

These data classes are used to represent any kind of immutable,
structured data used in the application, usually for cross module
exchange or configuration purposes.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

# Define a type alias for timezone-aware UTC datetime
# This is to help communicate intent better in type hints
UtcDateTime: TypeAlias = datetime


@dataclass(frozen=True)
class HostInfo:
    """
    Data class to hold platform information about a host.
    This includes the operating system, version, and package manager.
    Used for discovery and setup module results.
    """

    os: str
    version: str | None
    flavor: str | None
    package_manager: str | None
    is_supported: bool


@dataclass(frozen=True)
class HostState:
    """
    Data class to hold the state of a host.
    Used mainly for serialization to disk.

    Contains a state_version field to help with compatibility checks
    when loading cache from an earlier version of exosphere.

    It is not intended for this field to be specified directly, but
    instead to be incremented via its default value whenever the
    structure changes, to allow for easy migrations in load_or_create.
    """

    # Platform information (discovery results)
    os: str | None
    version: str | None
    flavor: str | None
    package_manager: str | None
    supported: bool | None

    # Host State
    online: bool
    updates: list["Update"]
    last_refresh: UtcDateTime | None

    # Version of state structure for compatibility checks
    # This should be incremented whenever the structure changes.
    state_version: int = 1


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
