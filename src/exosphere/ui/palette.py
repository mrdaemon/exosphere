"""
Command Palette Providers Module

Exposes per-host operations (ping, discover, refresh, sync+refresh) through
Textual's command palette.

Currently, we have three providers for host operations:

- HostCommandProvider: Scoped to the inventory screen, offers runnable
  operations on the currently selected host in the table.
- GlobalHostCommandProvider: Global scope, offers runnable operations
  on any host, and opens a secondary picker to select the target host
  from entries in the inventory, via fuzzy search or selection.
- GlobalAllHostsProvider: Global scope, offers runnable operations that
  target all hosts at once.

"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, ClassVar, cast

from textual.command import CommandPalette, DiscoveryHit, Hit, Hits, Provider

from exosphere import context
from exosphere.inventory import HostOperation
from exosphere.objects import Host

if TYPE_CHECKING:
    from exosphere.ui.app import ExosphereUi
    from exosphere.ui.inventory import InventoryScreen

logger = logging.getLogger("exosphere.ui.palette")


@dataclass(frozen=True)
class _PaletteCommand:
    """A palette-exposed host operation: a label and how to dispatch it.

    ``run`` takes the app and a host so it works from any screen. The
    compound "Sync & Refresh" is not a HostOperation member, so it gets
    its own dispatch closure here rather than living in the enum.
    """

    label: str
    run: Callable[["ExosphereUi", Host], None]


_COMMANDS: tuple[_PaletteCommand, ...] = (
    _PaletteCommand(
        "Ping",
        lambda app, host: app.run_host_operation(HostOperation.PING, host),
    ),
    _PaletteCommand(
        "Discover",
        lambda app, host: app.run_host_operation(HostOperation.DISCOVER, host),
    ),
    _PaletteCommand(
        "Refresh",
        lambda app, host: app.run_host_operation(HostOperation.REFRESH, host),
    ),
    _PaletteCommand(
        "Sync & Refresh",
        lambda app, host: app.run_host_sync_refresh(host),
    ),
)


class HostCommandProvider(Provider):
    """
    Inventory-scoped provider: operations on the selected host.

    Registered on InventoryScreen, and makes use of the screen's
    get_selected_host() method to target the currently highlighted
    host in the inventory data table.

    These hits are score-boosted so they appear above the global
    providers' entries (so the selected-host shortcut is at the top,
    not buried at the bottom of the palette).
    """

    # Palette sorts hits purely by score (descending).
    # Usually fixed at zero, so we boost it to float above the global
    # application level commands.
    SELECTED_HOST_BOOST = 100.0

    def _selected_items(self) -> list[tuple[str, Callable[[], None], str, str]]:
        """Build ``(display, runner, label, host_name)`` for the selected host."""
        screen = cast("InventoryScreen", self.screen)
        host = screen.get_selected_host()
        if host is None:
            return []

        app = cast("ExosphereUi", self.app)
        return [
            (
                f"{cmd.label} selected ({host.name})",
                partial(cmd.run, app, host),
                cmd.label,
                host.name,
            )
            for cmd in _COMMANDS
        ]

    async def discover(self) -> Hits:
        # Yield an artifically weighted hit
        for display, runner, label, host_name in self._selected_items():
            yield Hit(
                self.SELECTED_HOST_BOOST,
                display,
                runner,
                text=display,
                help=f"{label} on host '{host_name}'",
            )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, runner, label, host_name in self._selected_items():
            score = matcher.match(display)
            if score > 0:
                yield Hit(
                    score + self.SELECTED_HOST_BOOST,
                    matcher.highlight(display),
                    runner,
                    text=display,
                    help=f"{label} on host '{host_name}'",
                )


class GlobalHostCommandProvider(Provider):
    """
    Global provider: All operations, with a secondary host picker.

    Opens a secondary host picker palette that can be fuzzy searched.
    """

    def _open_picker(self, command: _PaletteCommand) -> None:
        """Push a second palette to choose a host from"""
        self.app.push_screen(
            CommandPalette(
                providers=[PICKERS[command.label]],
                placeholder=f"Select a host to {command.label}…",
            )
        )

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        return [
            (f"{cmd.label}…", partial(self._open_picker, cmd), cmd.label)
            for cmd in _COMMANDS
        ]

    async def discover(self) -> Hits:
        for display, runner, label in self._items():
            yield DiscoveryHit(
                display, runner, help=f"Select a host to {label.lower()}"
            )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, runner, label in self._items():
            score = matcher.match(display)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(display),
                    runner,
                    help=f"Select a host to {label.lower()}",
                )


class GlobalAllHostsProvider(Provider):
    """
    Global provider: batch operations on all hosts

    Target is always all hosts, surfaces the same operations as
    the rest of Exosphere, through the same mechanisms as the rest of
    the TUI, ensuring consistency.
    """

    def _items(self) -> list[tuple[str, Callable[[], None]]]:
        app = cast("ExosphereUi", self.app)
        return [
            ("Ping all hosts", partial(app.run_host_operation_all, HostOperation.PING)),
            (
                "Discover all hosts",
                partial(app.run_host_operation_all, HostOperation.DISCOVER),
            ),
            (
                "Refresh all hosts",
                partial(app.run_host_operation_all, HostOperation.REFRESH),
            ),
            ("Sync & Refresh all hosts", app.run_sync_refresh_all),
        ]

    async def discover(self) -> Hits:
        for display, runner in self._items():
            yield DiscoveryHit(display, runner, help=display)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, runner in self._items():
            score = matcher.match(display)
            if score > 0:
                yield Hit(score, matcher.highlight(display), runner, help=display)


class HostPickerProvider(Provider):
    """
    Secondary Host Picker provider: host selection for single commands

    The operation is carried out through ``palette_command`` on the
    concrete subclass, since Textual instantiates providers itself and
    we can't really inject per-instance state. It's a bit of a hack,
    but it works.
    """

    palette_command: ClassVar[_PaletteCommand]

    def _host_items(self) -> list[tuple[str, Callable[[], None]]]:
        inventory = context.inventory
        if inventory is None:
            return []

        app = cast("ExosphereUi", self.app)
        run = self.palette_command.run
        return [(host.name, partial(run, app, host)) for host in inventory.hosts]

    async def discover(self) -> Hits:
        label = self.palette_command.label
        for name, runner in self._host_items():
            yield DiscoveryHit(name, runner, help=f"{label} on host '{name}'")

    async def search(self, query: str) -> Hits:
        label = self.palette_command.label
        matcher = self.matcher(query)
        for name, runner in self._host_items():
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    runner,
                    help=f"{label} on host '{name}'",
                )


def _make_picker(command: _PaletteCommand) -> type[HostPickerProvider]:
    """Build a HostPickerProvider subclass bound to a single command."""
    safe = command.label.replace(" ", "").replace("&", "And")
    return cast(
        type[HostPickerProvider],
        type(f"HostPicker_{safe}", (HostPickerProvider,), {"palette_command": command}),
    )


# One picker provider class per command, keyed by label.
# This is kept public since it deeply lubricates testing.
PICKERS: dict[str, type[HostPickerProvider]] = {
    cmd.label: _make_picker(cmd) for cmd in _COMMANDS
}
