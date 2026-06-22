import pytest

from exosphere.commands import connections as connections_module
from exosphere.commands import utils as utils_module
from exosphere.config import Configuration


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the connections command module."""
    patch_console(connections_module)


@pytest.fixture(autouse=True)
def _interactive(mocker):
    """Patch context to simulate interactive mode being used"""
    mocker.patch.object(utils_module.context, "interactive", True)


@pytest.fixture
def mock_inventory(mocker):
    """
    Create a fake inventory with test hosts wired into the context.

    The fake inventory resolves host names off its own ``hosts`` list so the
    HostArg converter works for commands invoked with specific names.
    """
    mock_host1 = mocker.Mock()
    mock_host1.name = "webserver"
    mock_host1.ip = "192.168.1.10"
    mock_host1.port = 22
    mock_host1.is_connected = True
    mock_host1.connection_last_used = 1234567890.0  # Active connection

    mock_host2 = mocker.Mock()
    mock_host2.name = "dbserver"
    mock_host2.ip = "192.168.1.20"
    mock_host2.port = 22
    mock_host2.is_connected = False
    mock_host2.connection_last_used = None  # No active connection

    mock_host3 = mocker.Mock()
    mock_host3.name = "appserver"
    mock_host3.ip = "192.168.1.30"
    mock_host3.port = 22
    mock_host3.is_connected = True
    mock_host3.connection_last_used = 1234567850.0  # Active connection (different age)

    mock_inventory = mocker.Mock()
    mock_inventory.hosts = [mock_host1, mock_host2, mock_host3]
    mock_inventory.get_host.side_effect = lambda name: next(
        (h for h in mock_inventory.hosts if h.name == name), None
    )

    mocker.patch.object(utils_module.context, "inventory", mock_inventory)
    return mock_inventory


class TestShowCommand:
    """Tests for connections show command."""

    def test_show_with_pipelining_disabled(self, mocker, capsys):
        """Test that show command fails when pipelining is disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = False
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(["show"], result_action="return_value")

        err = capsys.readouterr().err
        assert code == 2  # Application error: feature disabled
        assert "SSH Pipelining is currently disabled" in err
        assert "No persistent connections" in err

    def test_show_all_hosts(self, mocker, mock_inventory, capsys):
        """Test showing connection state for all hosts."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 600
        config["options"]["ssh_pipelining_reap_interval"] = 60
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Mock time to get predictable idle times
        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        code = connections_module.app(["show"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0

        # Table headers
        assert "Host" in out
        assert "IP" in out
        assert "Port" in out
        assert "Idle" in out
        assert "State" in out

        # Hosts
        assert "webserver" in out
        assert "192.168.1.10" in out
        assert "dbserver" in out
        assert "appserver" in out

        # States
        assert "Connected" in out
        assert "Inactive" in out

    def test_show_specific_hosts(self, mocker, mock_inventory, capsys):
        """Test showing connection state for specific hosts."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 600
        config["options"]["ssh_pipelining_reap_interval"] = 60
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        code = connections_module.app(
            ["show", "webserver"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "webserver" in out
        assert "192.168.1.10" in out
        assert "dbserver" not in out
        assert "appserver" not in out

    def test_show_no_hosts(self, mocker, mock_inventory, capsys):
        """Test show command with an empty inventory."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mock_inventory.hosts = []

        code = connections_module.app(["show"], result_action="return_value")

        assert code == 1  # Input error: no hosts
        assert "No hosts found in inventory." in capsys.readouterr().err

    def test_show_expiring_connection(self, mocker, mock_inventory, capsys):
        """Test that connections exceeding lifetime are marked as expiring."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 10
        config["options"]["ssh_pipelining_reap_interval"] = 5
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Set current time so connection age exceeds lifetime
        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        mock_inventory.hosts = [mock_inventory.hosts[0]]

        code = connections_module.app(["show"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "webserver" in out
        assert "Expiring" in out

    @pytest.mark.parametrize("option", ["--active", "-a"], ids=["long", "short"])
    def test_show_active_only_flag(self, mocker, mock_inventory, option, capsys):
        """Test show command with --active flag."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 600
        config["options"]["ssh_pipelining_reap_interval"] = 60
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        code = connections_module.app(["show", option], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0

        assert "webserver" in out
        assert "appserver" in out
        assert "dbserver" not in out  # No active connection

        # Table title
        assert "(Active Only)" in out

    @pytest.mark.parametrize("option", ["--active", "-a"], ids=["long", "short"])
    def test_show_active_only_no_active_connections(
        self, mocker, mock_inventory, option, capsys
    ):
        """Test show --active when no hosts have active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Only the host with no active connection
        mock_inventory.hosts = [mock_inventory.hosts[1]]

        code = connections_module.app(["show", option], result_action="return_value")

        assert code == 0
        assert "No active connections" in capsys.readouterr().out


class TestCloseCommand:
    """Tests for connections close command."""

    def test_close_with_pipelining_disabled(self, mocker, capsys):
        """Test that close command fails when pipelining is disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = False
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(["close"], result_action="return_value")

        err = capsys.readouterr().err
        assert code == 2  # Application error: feature disabled
        assert "SSH Pipelining is currently disabled" in err
        assert "No persistent connections" in err

    def test_close_all_connections(self, mocker, mock_inventory, capsys):
        """Test closing all active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(["close"], result_action="return_value")

        assert code == 0
        assert mock_inventory.hosts[0].close.called
        assert not mock_inventory.hosts[1].close.called  # No active connection
        assert mock_inventory.hosts[2].close.called
        assert "Closed 2 active connection(s)" in capsys.readouterr().out

    def test_close_specific_host(self, mocker, mock_inventory, capsys):
        """Test closing connection for a specific host."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(
            ["close", "webserver"], result_action="return_value"
        )

        assert code == 0
        assert mock_inventory.hosts[0].close.called
        assert "Closed 1 active connection(s)" in capsys.readouterr().out

    @pytest.mark.parametrize("option", ["--verbose", "-v"], ids=["long", "short"])
    def test_close_verbose_mode(self, mocker, mock_inventory, option, capsys):
        """Test close command in verbose mode."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(["close", option], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0

        assert mock_inventory.hosts[0].close.called
        assert mock_inventory.hosts[2].close.called

        # Names should be displayed
        assert "webserver" in out
        assert "appserver" in out

    def test_close_no_active_connections(self, mocker, mock_inventory):
        """Test closing when no hosts have active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Only the host with no active connection
        mock_inventory.hosts = [mock_inventory.hosts[1]]

        code = connections_module.app(["close"], result_action="return_value")

        assert code == 0
        assert not mock_inventory.hosts[0].close.called

    def test_close_no_hosts(self, mocker, mock_inventory, capsys):
        """Test close command with an empty inventory."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mock_inventory.hosts = []

        code = connections_module.app(["close"], result_action="return_value")

        assert code == 1  # Input error: no hosts
        assert "No hosts found in inventory." in capsys.readouterr().err

    @pytest.mark.parametrize("option", ["--verbose", "-v"], ids=["long", "short"])
    def test_close_verbose_with_inactive_hosts(
        self, mocker, mock_inventory, option, capsys
    ):
        """Test verbose mode with mix of active and inactive hosts."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        code = connections_module.app(["close", option], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0

        assert mock_inventory.hosts[0].close.called
        assert not mock_inventory.hosts[1].close.called  # No active connection
        assert mock_inventory.hosts[2].close.called

        # Skipped message shows up in verbose mode
        assert "Skipped 1 host(s)" in out


class TestConnectionsCommands:
    """Integration tests for connections commands."""

    @pytest.mark.parametrize("command", ["show", "close"], ids=["show", "close"])
    def test_commands_bail_with_uninitialized_inventory(self, mocker, command, capsys):
        """Test that commands bail out with an uninitialized inventory."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Uninitialized inventory: get_hosts_or_all -> get_inventory() aborts
        mocker.patch.object(utils_module.context, "inventory", None)

        with pytest.raises(SystemExit) as exc_info:
            connections_module.app([command])

        assert exc_info.value.code == 2  # Application error
        assert "Inventory is not initialized" in capsys.readouterr().err

    @pytest.mark.parametrize("command", ["show", "close"], ids=["show", "close"])
    def test_commands_bail_outside_interactive(self, mocker, command, capsys):
        """Interactive-only commands refuse to run from a one-shot CLI."""
        mocker.patch.object(utils_module.context, "interactive", False)

        with pytest.raises(SystemExit) as exc_info:
            connections_module.app([command])

        assert exc_info.value.code == 2  # Application error: wrong context
        assert "only available in Interactive Mode" in capsys.readouterr().err
