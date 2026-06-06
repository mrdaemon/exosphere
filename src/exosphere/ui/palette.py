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

from textual.command import CommandPalette, Hit, Hits, Provider

from exosphere import context
from exosphere.objects import Host, HostOperation

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


class _PaletteProvider(Provider):
    """
    Common base for palette providers exposing host operations

    Palette providers just implement `_items` and return a list of
    ``(display, runner, help)`` triples, which this renders as palette
    hits for both Discover and Typed search views, so all the matcher
    boilerplate lives in one place.

    Hits carry the BOOST score from this base class, so a subclass can
    float results above others, since textual palettes sort purely by
    hit score.
    """

    # Score added to provider hits - zero is default
    # Increase to float results above others
    BOOST: ClassVar[float] = 0.0

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        """Return ``(display, runner, help)`` triples."""
        raise NotImplementedError

    async def discover(self) -> Hits:
        for display, runner, help_text in self._items():
            yield Hit(self.BOOST, display, runner, text=display, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, runner, help_text in self._items():
            score = matcher.match(display)
            if score > 0:
                yield Hit(
                    score + self.BOOST,
                    matcher.highlight(display),
                    runner,
                    text=display,
                    help=help_text,
                )


class HostCommandProvider(_PaletteProvider):
    """
    Inventory-scoped provider: operations on the selected host.

    Registered on InventoryScreen and makes use of the screen's
    get_selected_host() method to target the currently highlighted
    host in the inventory data table.

    Hits are score-boosted so they appear above the global
    providers' entries (so the selected host shortcut is at the top
    of the results, but burried at the bottom of the palette).
    """

    BOOST = 100.0

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        screen = cast("InventoryScreen", self.screen)
        host = screen.get_selected_host()
        if host is None:
            return []

        app = cast("ExosphereUi", self.app)

        return [
            (
                f"{cmd.label} selected ({host.name})",
                partial(cmd.run, app, host),
                f"{cmd.label} on host '{host.name}'",
            )
            for cmd in _COMMANDS
        ]


class GlobalHostCommandProvider(_PaletteProvider):
    """
    Global provider: All operations,i with a secondary host picker.

    The secondary host picker palette can be fuzzy searched.
    """

    def _open_picker(self, command: _PaletteCommand) -> None:
        """Push a second palette to fuzzy pick the target host."""
        self.app.push_screen(
            CommandPalette(
                providers=[PICKERS[command.label]],
                placeholder=f"Select a host to {command.label}…",
            )
        )

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        return [
            (
                f"{cmd.label}…",
                partial(self._open_picker, cmd),
                f"Select a host to {cmd.label.lower()}",
            )
            for cmd in _COMMANDS
        ]


class GlobalAllHostsProvider(_PaletteProvider):
    """
    Global provider: batch operations targeting all hosts at once.

    Surfaces the same operations as the rest of the TUI through the same
    dispatch mechanisms, for consistency.
    """

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        app = cast("ExosphereUi", self.app)
        items: list[tuple[str, Callable[[], None]]] = [
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

        return [(display, runner, display) for display, runner in items]


class HostPickerProvider(_PaletteProvider):
    """
    Secondary Host Picker: host selection for single commands.

    The operation is carried out through ``palette_command`` on a
    concrete subclass (built by :func:`_make_picker`), since Textual
    instantiates providers itself and we can't really inject
    per-instance state. A bit of a hack, but it works.
    """

    palette_command: ClassVar[_PaletteCommand]

    def _items(self) -> list[tuple[str, Callable[[], None], str]]:
        inventory = context.inventory
        if inventory is None:
            return []

        app = cast("ExosphereUi", self.app)
        cmd = self.palette_command

        return [
            (
                host.name,
                partial(cmd.run, app, host),
                f"{cmd.label} on host '{host.name}'",
            )
            for host in inventory.hosts
        ]


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
