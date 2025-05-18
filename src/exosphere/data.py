# Data Types and Classes

from dataclasses import dataclass
from typing import Optional


@dataclass
class HostInfo:
    """
    Data class to hold platform information about a host.
    This includes the operating system, version, and package manager.
    """

    os: str
    version: str
    flavor: str
    package_manager: str


@dataclass
class Update:
    """
    Data class to hold information about a software update.
    Includes the name of the software, the current version,
    new version, and optionally a source.
    """

    name: str
    current_version: str
    new_version: str
    source: Optional[str] = None
