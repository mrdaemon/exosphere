"""
Tests for the command palette host-operation providers.
"""

import asyncio
from typing import Any

import pytest
from textual.command import CommandPalette

from exosphere import context
from exosphere.inventory import HostOperation
from exosphere.ui.palette import (
    PICKERS,
    GlobalAllHostsProvider,
    GlobalHostCommandProvider,
    HostCommandProvider,
)


def _collect(agen) -> list[Any]:
    """Drain an async generator into a list using a fresh event loop."""

    async def run() -> list[Any]:
        return [item async for item in agen]

    return asyncio.run(run())


@pytest.fixture
def mock_screen(mocker):
    """
    Stand-in screen. Provider.app resolves to screen.app, so
    mock_screen.app is where dispatch/push calls land.
    """
    return mocker.MagicMock()


class TestHostCommandProvider:
    """Inventory-scoped: operations on the selected host."""

    @pytest.fixture
    def provider(self, mock_screen):
        return HostCommandProvider(mock_screen)

    def test_discover_offers_selected_host_ops(self, mocker, provider, mock_screen):
        host = mocker.Mock()
        host.name = "web3"
        mock_screen.get_selected_host.return_value = host

        hits = _collect(provider.discover())

        # Hits have a boosted score, and must be handled by
        # prompt instead of display
        assert [str(h.prompt) for h in hits] == [
            "Ping selected (web3)",
            "Discover selected (web3)",
            "Refresh selected (web3)",
            "Sync & Refresh selected (web3)",
        ]

    def test_discover_hits_outrank_global_providers(
        self, mocker, provider, mock_screen
    ):
        """Selected-host hits score above the global providers' hits."""
        from exosphere.ui.palette import GlobalAllHostsProvider

        host = mocker.Mock()
        host.name = "web3"
        mock_screen.get_selected_host.return_value = host

        selected = _collect(provider.discover())
        global_hits = _collect(GlobalAllHostsProvider(mock_screen).discover())

        assert min(h.score for h in selected) > max(h.score for h in global_hits)

    def test_discover_no_selected_host(self, provider, mock_screen):
        mock_screen.get_selected_host.return_value = None
        assert _collect(provider.discover()) == []

    def test_search_filters_selected_ops(self, mocker, provider, mock_screen):
        host = mocker.Mock()
        host.name = "web3"
        mock_screen.get_selected_host.return_value = host

        hits = _collect(provider.search("ping"))

        assert any("Ping selected (web3)" in str(h.match_display) for h in hits)

    def test_command_dispatches_on_selected_host(self, mocker, provider, mock_screen):
        host = mocker.Mock()
        host.name = "web3"
        mock_screen.get_selected_host.return_value = host

        hits = _collect(provider.discover())

        hits[0].command()  # Ping
        mock_screen.app.run_host_operation.assert_called_once_with(
            HostOperation.PING, host
        )

        hits[-1].command()  # Sync & Refresh -> compound helper
        mock_screen.app.run_host_sync_refresh.assert_called_once_with(host)


class TestGlobalHostCommandProvider:
    """App-scoped: each operation, opening a secondary host picker."""

    @pytest.fixture
    def provider(self, mock_screen):
        return GlobalHostCommandProvider(mock_screen)

    def test_discover_offers_each_operation(self, provider):
        hits = _collect(provider.discover())
        assert [str(h.display) for h in hits] == [
            "Ping…",
            "Discover…",
            "Refresh…",
            "Sync & Refresh…",
        ]

    def test_search_matches_by_label(self, provider):
        hits = _collect(provider.search("refresh"))
        assert any("Refresh" in str(h.match_display) for h in hits)

    def test_command_opens_host_picker_palette(self, provider, mock_screen):
        hits = _collect(provider.discover())

        hits[0].command()  # Ping...

        mock_screen.app.push_screen.assert_called_once()
        pushed = mock_screen.app.push_screen.call_args[0][0]
        assert isinstance(pushed, CommandPalette)


class TestGlobalAllHostsProvider:
    """App-scoped: operations across all hosts at once."""

    @pytest.fixture
    def provider(self, mock_screen):
        return GlobalAllHostsProvider(mock_screen)

    def test_discover_offers_all_hosts_operations(self, provider):
        hits = _collect(provider.discover())
        assert [str(h.display) for h in hits] == [
            "Ping all hosts",
            "Discover all hosts",
            "Refresh all hosts",
            "Sync & Refresh all hosts",
        ]

    def test_search_matches(self, provider):
        hits = _collect(provider.search("refresh all"))
        assert any("Refresh all hosts" in str(h.match_display) for h in hits)

    def test_command_dispatches_atomic_all(self, provider, mock_screen):
        hits = _collect(provider.discover())
        hits[0].command()  # Ping all hosts
        mock_screen.app.run_host_operation_all.assert_called_once_with(
            HostOperation.PING
        )

    def test_command_dispatches_compound_all(self, provider, mock_screen):
        hits = _collect(provider.discover())
        hits[-1].command()  # Sync & Refresh all hosts
        mock_screen.app.run_sync_refresh_all.assert_called_once_with()


class TestHostPickerProvider:
    """Secondary palette: pick a host for a bound operation."""

    @pytest.fixture
    def two_hosts(self, mocker):
        h1 = mocker.Mock()
        h1.name = "web1"
        h2 = mocker.Mock()
        h2.name = "db2"
        mocker.patch.object(context, "inventory", mocker.Mock(hosts=[h1, h2]))
        return h1, h2

    def test_discover_lists_all_hosts(self, mock_screen, two_hosts):
        picker = PICKERS["Ping"](mock_screen)
        hits = _collect(picker.discover())
        assert [str(h.display) for h in hits] == ["web1", "db2"]

    def test_search_fuzzy_matches_host(self, mock_screen, two_hosts):
        picker = PICKERS["Ping"](mock_screen)
        hits = _collect(picker.search("db"))
        assert [str(h.match_display) for h in hits] == ["db2"]

    def test_no_inventory_yields_nothing(self, mocker, mock_screen):
        mocker.patch.object(context, "inventory", None)
        picker = PICKERS["Ping"](mock_screen)
        assert _collect(picker.discover()) == []

    def test_pick_dispatches_atomic_operation(self, mock_screen, two_hosts):
        _, h2 = two_hosts
        picker = PICKERS["Refresh"](mock_screen)

        hits = _collect(picker.discover())
        hits[1].command()  # pick db2

        mock_screen.app.run_host_operation.assert_called_once_with(
            HostOperation.REFRESH, h2
        )

    def test_pick_dispatches_compound_sync_refresh(self, mock_screen, two_hosts):
        h1, _ = two_hosts
        picker = PICKERS["Sync & Refresh"](mock_screen)

        hits = _collect(picker.discover())
        hits[0].command()  # pick web1

        mock_screen.app.run_host_sync_refresh.assert_called_once_with(h1)
