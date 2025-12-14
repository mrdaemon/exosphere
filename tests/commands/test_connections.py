import pytest
from typer.testing import CliRunner

from exosphere.commands import connections as connections_module
from exosphere.config import Configuration

runner = CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture
def mock_inventory(mocker):
    """
    Create a mock inventory with test hosts.
    """
    mock_host1 = mocker.Mock()
    mock_host1.name = "webserver"
    mock_host1.ip = "192.168.1.10"
    mock_host1.port = 22
    mock_host1.connection_last_used = 1234567890.0  # Active connection

    mock_host2 = mocker.Mock()
    mock_host2.name = "dbserver"
    mock_host2.ip = "192.168.1.20"
    mock_host2.port = 22
    mock_host2.connection_last_used = None  # No active connection

    mock_host3 = mocker.Mock()
    mock_host3.name = "appserver"
    mock_host3.ip = "192.168.1.30"
    mock_host3.port = 22
    mock_host3.connection_last_used = 1234567850.0  # Active connection (different age)

    mock_inventory = mocker.Mock()
    mock_inventory.hosts = [mock_host1, mock_host2, mock_host3]

    return mock_inventory


class TestShowCommand:
    """Tests for connections show command."""

    def test_show_with_pipelining_disabled(self, mocker):
        """Test that show command fails when pipelining is disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = False
        mocker.patch("exosphere.commands.connections.app_config", config)

        result = runner.invoke(connections_module.app, ["show"])

        assert result.exit_code == 1
        assert "SSH Pipelining is currently disabled" in result.stderr
        assert "No persistent connections" in result.stderr

    def test_show_all_hosts(self, mocker, mock_inventory):
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

        # Mock get_hosts_or_error to return all hosts
        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=mock_inventory.hosts,
        )

        result = runner.invoke(connections_module.app, ["show"])

        assert result.exit_code == 0

        # Table headers
        assert "Host" in result.stdout
        assert "IP" in result.stdout
        assert "Port" in result.stdout
        assert "Idle" in result.stdout
        assert "State" in result.stdout

        # Hosts
        assert "webserver" in result.stdout
        assert "192.168.1.10" in result.stdout
        assert "dbserver" in result.stdout
        assert "appserver" in result.stdout

        # States
        assert "Connected" in result.stdout
        assert "Inactive" in result.stdout

    def test_show_specific_hosts(self, mocker, mock_inventory):
        """Test showing connection state for specific hosts."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 600
        config["options"]["ssh_pipelining_reap_interval"] = 60
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        # Mock get_hosts_or_error to return specific hosts
        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=[mock_inventory.hosts[0]],
        )

        result = runner.invoke(connections_module.app, ["show", "webserver"])

        assert result.exit_code == 0
        assert "webserver" in result.stdout
        assert "192.168.1.10" in result.stdout
        assert "dbserver" not in result.stdout
        assert "appserver" not in result.stdout

    def test_show_no_hosts(self, mocker):
        """Test show command when get_hosts_or_error returns None."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error", return_value=None
        )

        result = runner.invoke(connections_module.app, ["show"])

        assert result.exit_code == 2  # Argument error

    def test_show_expiring_connection(self, mocker, mock_inventory):
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

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=[mock_inventory.hosts[0]],
        )

        result = runner.invoke(connections_module.app, ["show"])

        assert result.exit_code == 0
        assert "webserver" in result.stdout
        assert "Expiring" in result.stdout

    @pytest.mark.parametrize("option", ["--active", "-a"], ids=["long", "short"])
    def test_show_active_only_flag(self, mocker, mock_inventory, option):
        """Test show command with --active flag."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        config["options"]["ssh_pipelining_lifetime"] = 600
        config["options"]["ssh_pipelining_reap_interval"] = 60
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.time.time", return_value=1234567900.0
        )

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=mock_inventory.hosts,
        )

        result = runner.invoke(connections_module.app, ["show", option])

        assert result.exit_code == 0

        assert "webserver" in result.stdout
        assert "appserver" in result.stdout
        assert "dbserver" not in result.stdout  # No active connection

        # Table title
        assert "(Active Only)" in result.stdout

    @pytest.mark.parametrize("option", ["--active", "-a"], ids=["long", "short"])
    def test_show_active_only_no_active_connections(
        self, mocker, mock_inventory, option
    ):
        """Test show --active when no hosts have active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=[mock_inventory.hosts[1]],  # host with no connection
        )

        result = runner.invoke(connections_module.app, ["show", option])

        assert result.exit_code == 0
        assert "No active connections" in result.stdout


class TestCloseCommand:
    """Tests for connections close command."""

    def test_close_with_pipelining_disabled(self, mocker):
        """Test that close command fails when pipelining is disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = False
        mocker.patch("exosphere.commands.connections.app_config", config)

        result = runner.invoke(connections_module.app, ["close"])

        assert result.exit_code == 1
        assert "SSH Pipelining is currently disabled" in result.stderr
        assert "No persistent connections" in result.stderr

    def test_close_all_connections(self, mocker, mock_inventory):
        """Test closing all active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=mock_inventory.hosts,
        )

        result = runner.invoke(connections_module.app, ["close"])

        assert result.exit_code == 0
        assert mock_inventory.hosts[0].close.called
        assert not mock_inventory.hosts[1].close.called  # No active connection
        assert mock_inventory.hosts[2].close.called
        assert "Closed 2 active connection(s)" in result.stdout

    def test_close_specific_host(self, mocker, mock_inventory):
        """Test closing connection for a specific host."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=[mock_inventory.hosts[0]],  # webserver only
        )

        result = runner.invoke(connections_module.app, ["close", "webserver"])

        assert result.exit_code == 0
        assert mock_inventory.hosts[0].close.called
        assert "Closed 1 active connection(s)" in result.stdout

    @pytest.mark.parametrize("option", ["--verbose", "-v"], ids=["long", "short"])
    def test_close_verbose_mode(self, mocker, mock_inventory, option):
        """Test close command in verbose mode."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=mock_inventory.hosts,
        )

        result = runner.invoke(connections_module.app, ["close", option])

        assert result.exit_code == 0

        assert mock_inventory.hosts[0].close.called
        assert mock_inventory.hosts[2].close.called

        # Names shuold be displayed
        assert "webserver" in result.stdout
        assert "appserver" in result.stdout

    def test_close_no_active_connections(self, mocker, mock_inventory):
        """Test closing when no hosts have active connections."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        # Return only the host with no active connection
        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=[mock_inventory.hosts[1]],  # dbserver with no connection
        )

        result = runner.invoke(connections_module.app, ["close"])

        assert result.exit_code == 0
        assert not mock_inventory.hosts[1].close.called

    def test_close_no_hosts(self, mocker):
        """Test close command when get_hosts_or_error returns None."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error", return_value=None
        )

        result = runner.invoke(connections_module.app, ["close"])

        assert result.exit_code == 2  # Argument error

    @pytest.mark.parametrize("option", ["--verbose", "-v"], ids=["long", "short"])
    def test_close_verbose_with_inactive_hosts(self, mocker, mock_inventory, option):
        """Test verbose mode with mix of active and inactive hosts."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error",
            return_value=mock_inventory.hosts,  # Mix of active and inactive
        )

        result = runner.invoke(connections_module.app, ["close", option])

        assert result.exit_code == 0

        assert mock_inventory.hosts[0].close.called
        assert not mock_inventory.hosts[1].close.called  # No active connection
        assert mock_inventory.hosts[2].close.called

        # Skipped message shows up in verbose mode
        assert "Skipped 1 host(s)" in result.stdout


class TestConnectionsCommands:
    """Integration tests for connections commands."""

    def test_commands_bail_with_uninitialized_inventory(self, mocker):
        """Test that commands handle uninitialized inventory gracefully."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = True
        mocker.patch("exosphere.commands.connections.app_config", config)

        # get_hosts_or_error should handle this and exit
        mocker.patch(
            "exosphere.commands.connections.get_hosts_or_error", return_value=None
        )

        result_show = runner.invoke(connections_module.app, ["show"])
        result_close = runner.invoke(connections_module.app, ["close"])

        assert result_show.exit_code == 2
        assert result_close.exit_code == 2
