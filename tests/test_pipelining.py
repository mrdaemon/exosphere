"""
Tests for the pipelining module.
"""

import time

import pytest

from exosphere.config import Configuration
from exosphere.pipelining import ConnectionReaper


class TestConnectionReaper:
    @pytest.fixture
    def mock_config(self, mocker, caplog):
        """Mock app_config with pipelining enabled."""
        caplog.set_level("DEBUG")
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 310
        config["options"]["ssh_pipelining_reap_interval"] = 27

        mocker.patch("exosphere.pipelining.app_config", config)
        return config

    @pytest.fixture
    def mock_inventory(self, mocker):
        """Mock inventory and patch context.inventory."""
        inventory = mocker.MagicMock()
        mocker.patch("exosphere.pipelining.context.inventory", inventory)
        return inventory

    @pytest.fixture
    def mock_host(self, mocker):
        """Create a mock host with connection tracking."""
        host = mocker.MagicMock()
        host.name = "test-host"
        host.connection_last_used = None
        return host

    def test_reaper_init(self, mock_config):
        """Test ConnectionReaper initialization."""
        reaper = ConnectionReaper()

        # Ensure properties are set from config
        assert reaper.check_interval == 27
        assert reaper.max_lifetime == 310

    def test_reaper_start_without_inventory(self, mocker, mock_config, caplog):
        """Test that reaper logs error when inventory not initialized."""
        mocker.patch("exosphere.pipelining.context.inventory", None)

        reaper = ConnectionReaper()
        reaper.start()

        assert "inventory not initialized" in caplog.text.lower()
        assert not reaper.is_running

    def test_reaper_start_with_pipelining_disabled(
        self, mocker, mock_inventory, caplog
    ):
        """Test that reaper doesn't start when pipelining is disabled."""
        caplog.set_level("DEBUG")
        config = Configuration()
        config["options"]["ssh_pipelining"] = False
        config["options"]["ssh_pipelining_lifetime"] = 300
        config["options"]["ssh_pipelining_reap_interval"] = 60

        mocker.patch("exosphere.pipelining.app_config", config)

        reaper = ConnectionReaper()
        reaper.start()

        assert "pipelining disabled" in caplog.text.lower()
        assert not reaper.is_running

    def test_reaper_start_success(self, mocker, mock_config, mock_inventory):
        """Test successful reaper thread start."""
        reaper = ConnectionReaper()

        assert not reaper.is_running

        reaper.start()

        assert reaper.is_running

        # Cleanup
        reaper.stop()

    def test_reaper_start_already_running(
        self, mocker, mock_config, mock_inventory, caplog
    ):
        """Test that starting an already running reaper logs a warning."""
        reaper = ConnectionReaper()
        reaper.start()

        assert reaper.is_running

        reaper.start()

        assert "already running" in caplog.text.lower()

        # Ensure existing thread is still running
        assert reaper.is_running

        # Cleanup
        reaper.stop()

    def test_reaper_warns_on_short_lifetime(self, mocker, mock_inventory, caplog):
        """Test warning when ssh_pipelining_lifetime is too short."""
        caplog.set_level("DEBUG")
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 10  # Very short

        mocker.patch("exosphere.pipelining.app_config", config)

        reaper = ConnectionReaper()
        reaper.start()

        assert "is very short!" in caplog.text.lower()
        assert "10s" in caplog.text

        # Should start anyways, because I'm not your dad
        assert reaper.is_running

        # Cleanup
        reaper.stop()

    def test_reaper_warns_on_interval_too_long(self, mocker, mock_inventory, caplog):
        """Test warning when ssh_pipelining_reap_interval >= lifetime."""
        caplog.set_level("DEBUG")
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 120
        config["options"]["ssh_pipelining_reap_interval"] = 120  # Equal to lifetime

        mocker.patch("exosphere.pipelining.app_config", config)

        reaper = ConnectionReaper()
        reaper.start()

        assert "greater than or equal to" in caplog.text.lower()
        assert "may not be closed as expected" in caplog.text.lower()

        # Should start anyways
        assert reaper.is_running

        # Cleanup
        reaper.stop()

    def test_reaper_stop_not_running(self, mock_config, caplog):
        """Test stopping a reaper that isn't running."""
        caplog.set_level("DEBUG")
        reaper = ConnectionReaper()

        assert not reaper.is_running

        reaper.stop()

        assert "not running" in caplog.text.lower()

    def test_reaper_stop_gracefully(self, mocker, mock_config, mock_inventory):
        """Test that reaper stops gracefully."""
        reaper = ConnectionReaper()
        reaper.start()

        assert reaper.is_running

        # Stop should complete without hanging
        reaper.stop()

        assert not reaper.is_running

    @pytest.mark.parametrize(
        "last_used_offset, should_close",
        [
            (None, False),
            (400, True),
            (100, False),
        ],
        ids=["no_connection", "idle_connection", "recent_connection"],
    )
    def test_reaper_connection_lifetime_handling(
        self, mock_config, mock_inventory, mock_host, last_used_offset, should_close
    ):
        """
        Test that the reaper correctly handles various lifetimes
        """
        mock_inventory.hosts = [mock_host]

        if last_used_offset is None:
            mock_host.connection_last_used = None
        else:
            mock_host.connection_last_used = time.time() - last_used_offset

        reaper = ConnectionReaper()
        reaper.close_idle_connections()

        if should_close:
            mock_host.close.assert_called_once_with(clear=False)
        else:
            mock_host.close.assert_not_called()

    def test_reaper_handles_multiple_hosts(self, mock_config, mock_inventory, mocker):
        """Test that reaper correctly handles multiple hosts."""
        # Create hosts with different idle times
        host1 = mocker.MagicMock()
        host1.name = "host1"
        host1.connection_last_used = time.time() - 400

        host2 = mocker.MagicMock()
        host2.name = "host2"
        host2.connection_last_used = time.time() - 100

        host3 = mocker.MagicMock()
        host3.name = "host3"
        host3.connection_last_used = None

        mock_inventory.hosts = [host1, host2, host3]

        reaper = ConnectionReaper()
        reaper.close_idle_connections()

        # Only host1 should be closed
        host1.close.assert_called_once_with(clear=False)
        host2.close.assert_not_called()
        host3.close.assert_not_called()

    def test_reaper_handles_exceptions(
        self, mock_config, mock_inventory, mock_host, caplog
    ):
        """Test that reaper handles exceptions without crashing."""
        mock_inventory.hosts = [mock_host]
        mock_host.connection_last_used = time.time() - 400
        mock_host.close.side_effect = Exception("Test error")

        reaper = ConnectionReaper()
        reaper.close_idle_connections()

        assert "Error closing connection to test-host" in caplog.text

    def test_reaper_with_empty_inventory(self, mock_config, mock_inventory, caplog):
        """Test that reaper handles empty inventory gracefully."""
        caplog.set_level("DEBUG")
        mock_inventory.hosts = []

        reaper = ConnectionReaper()
        reaper.close_idle_connections()

        assert "no hosts" in caplog.text.lower()
