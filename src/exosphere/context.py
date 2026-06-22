"""
Context module for Exosphere

Global context, variables and other shared state objects used
throughout the Exosphere application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from filelock import FileLock

    from exosphere.inventory import Inventory
    from exosphere.pipelining import ConnectionReaper

inventory: Inventory | None = None
reaper: ConnectionReaper | None = None
confpath: str | None = None
cache_lock: FileLock | None = None
interactive: bool = False
