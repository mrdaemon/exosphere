import pytest
from typer.testing import CliRunner

from exosphere.commands import inventory as inventory_module
from exosphere.commands import utils as utils_module
from exosphere.config import Configuration
from exosphere.objects import Host

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_inventory(mocker):
    """
    Patch context inventory for all tests
    """
    fake_inventory = mocker.create_autospec(inventory_module.Inventory, instance=True)
    fake_inventory.hosts = []
    mocker.patch.object(utils_module.context, "inventory", fake_inventory)
    return fake_inventory


@pytest.fixture
def create_host(mocker):
    """
    Factory fixture to create Host autospec mocks with default values.
    """

    def _create_host(
        name="test-host",
        os="linux",
        flavor="debian",
        version="12",
        updates=None,
        security_updates=None,
        online=True,
        is_stale=False,
    ):
        host = mocker.create_autospec(Host, instance=True)
        host.name = name
        host.os = os
        host.flavor = flavor
        host.version = version
        host.updates = updates if updates is not None else []
        host.security_updates = security_updates if security_updates is not None else []
        host.online = online
        host.is_stale = is_stale
        return host

    return _create_host


class TestStatusCommand:
    """Tests for the status command"""

    def test_shows_table(self, create_host, mock_inventory):
        """
        Basic test for the status command to ensure it shows a table with host information.
        This is meant to be a somewhat comprehensive catch-all as first test.
        """
        host = create_host(name="host1", updates=[1, 2, 3, 4], security_updates=[1])

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "Host Status Overview" in result.output
        assert "host1" in result.output
        assert "linux" in result.output
        assert "debian" in result.output
        assert "12" in result.output
        assert "4" in result.output
        assert "1" in result.output
        assert "4 *" not in result.output  # No stale hosts
        assert "1 *" not in result.output  # No stale hosts
        assert "Online" in result.output
        assert "Offline" not in result.output

    def test_with_stale_hosts(self, create_host, mock_inventory):
        """
        Test the status command to ensure it correctly identifies stale hosts.
        """
        host = create_host(
            name="host1", updates=[1, 2, 3, 4], security_updates=[1], is_stale=True
        )

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "4 *" in result.output  # Stale hosts marked with *
        assert "1 *" in result.output  # Stale hosts marked with *

    def test_no_hosts(self, mocker, mock_inventory):
        """
        Test the status command to ensure it handles the case with no hosts gracefully.
        """
        mock_inventory.hosts = []

        # mock get_hosts_or_error to return None
        mocker.patch.object(utils_module, "get_hosts_or_error", return_value=None)

        result = runner.invoke(inventory_module.app, ["status"])

        assert "No hosts found in inventory." in result.output
        assert result.exit_code == 0

    def test_no_hosts_fallback(self, mocker, mock_inventory):
        """
        Test the status command to ensure it handles get_hosts_or_error returning None.
        """
        # mock get_hosts_or_error to return None
        mocker.patch.object(utils_module, "get_hosts_or_error", return_value=None)

        result = runner.invoke(inventory_module.app, ["status"])

        assert "No hosts found in inventory." in result.output
        assert result.exit_code == 0

    def test_with_specific_hosts(self, create_host, mock_inventory):
        """
        Test the status command with specific host names.
        """
        host1 = create_host(name="host1", updates=[1, 2, 3], security_updates=[1])
        host2 = create_host(name="host2", updates=[1, 2], security_updates=[])

        # Mock inventory.hosts to contain the hosts
        mock_inventory.hosts = [host1, host2]

        result = runner.invoke(inventory_module.app, ["status", "host1"])

        assert result.exit_code == 0
        assert "Host Status Overview" in result.output
        assert "host1" in result.output
        assert "host2" not in result.output  # Should not show host2

    def test_with_no_updates(self, create_host, mock_inventory):
        """
        Test the status command with a host that has no updates.
        """
        host = create_host(name="host1", updates=[], security_updates=[])

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "host1" in result.output
        assert (
            result.output.count("0") == 2
        )  # Should show 0 updates and security updates

    def test_with_security_updates(self, create_host, mock_inventory):
        """
        Test the status command displays security updates in red when present.
        """
        host = create_host(name="host1", updates=[1, 2, 3], security_updates=[1, 2])

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "2" in result.output  # Should show security update count

    def test_with_offline_host(self, create_host, mock_inventory):
        """
        Test the status command with an offline host.
        """
        host = create_host(
            name="host1", updates=[1, 2, 3], security_updates=[], online=False
        )

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "Offline" in result.output

    def test_with_undiscovered_host(self, create_host, mock_inventory):
        """
        Test the status command with unknown host properties.
        """
        host = create_host(
            name="host1",
            os=None,
            flavor=None,
            version=None,
            updates=[],
            security_updates=None,
        )

        mock_inventory.hosts = [host]

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "host1" in result.output
        assert "(unknown)" in result.output
        assert result.output.count("(unknown)") == 3
        assert "0" in result.output  # Should show 0 updates and security updates
        assert "*" in result.output  # Should show stale indicator out of the box

    def test_multiple_hosts_with_different_states(self, create_host, mock_inventory):
        """
        Test status command with multiple hosts having different online/stale states.
        """
        hosts = []

        # Online, fresh host
        host1 = create_host(
            name="server1",
            flavor="ubuntu",
            version="20.04",
            updates=[1, 2, 3],
            security_updates=[1],
        )
        hosts.append(host1)

        # Online, stale host
        host2 = create_host(
            name="server2",
            version="11",
            updates=[1, 2],
            security_updates=[],
            is_stale=True,
        )
        hosts.append(host2)

        # Offline host
        host3 = create_host(
            name="server3",
            flavor="centos",
            version="8",
            updates=[1],
            security_updates=[1],
            online=False,
        )
        hosts.append(host3)

        mock_inventory.hosts = hosts

        result = runner.invoke(inventory_module.app, ["status"])

        assert result.exit_code == 0
        assert "server1" in result.output
        assert "server2" in result.output
        assert "server3" in result.output
        assert "ubuntu" in result.output
        assert "centos" in result.output
        assert result.output.count("Online") == 2  # server1 and server2 are online
        assert result.output.count("Offline") == 1  # server3 is offline
        assert "2 *" in result.output  # Stale updates for server2


class TestSaveCommand:
    """Tests for the save command"""

    def test_success(self, mocker, mock_inventory):
        """
        Test the save command to ensure it calls the save_state method on the inventory.
        """
        mock_inventory.save_state = mocker.Mock()

        result = runner.invoke(inventory_module.app, ["save"])

        assert result.exit_code == 0
        mock_inventory.save_state.assert_called_once()

    def test_failure(self, mocker, mock_inventory):
        """
        Test the save command to ensure it handles exceptions raised by save_state.
        """
        mock_inventory.save_state = mocker.Mock(
            side_effect=Exception("Some write problem")
        )

        result = runner.invoke(inventory_module.app, ["save"])

        assert result.exit_code != 0
        assert "Error saving inventory state" in result.output
        assert "Some write problem" in result.output


class TestClearCommand:
    """Tests for the clear command"""

    def test_success(self, mocker, mock_inventory):
        """
        Test the clear command to ensure it clears the inventory.
        """
        mock_clear = mock_inventory.clear_state = mocker.Mock()

        result = runner.invoke(inventory_module.app, ["clear", "--force"])

        assert result.exit_code == 0
        mock_clear.assert_called_once()
        assert "Inventory state has been cleared" in result.output

    def test_no_force(self, mocker, mock_inventory):
        """
        Test the clear command to ensure it prompts for confirmation when --force is not used.
        """
        result = runner.invoke(inventory_module.app, ["clear"])

        assert result.exit_code != 0
        assert "Confirm [y/n]" in result.output

    def test_confirmation(self, mocker, mock_inventory):
        """
        Test the clear command to ensure it clears the inventory when confirmed.
        """
        mock_inventory.clear_state = mocker.Mock()

        result = runner.invoke(inventory_module.app, ["clear"], input="y\n")

        assert result.exit_code == 0
        mock_inventory.clear_state.assert_called_once()
        assert "Inventory state has been cleared" in result.output

    def test_cancelled(self, mocker, mock_inventory):
        """
        Test the clear command to ensure it does not clear the inventory when cancelled.
        """
        mock_inventory.clear_state = mocker.Mock()

        result = runner.invoke(inventory_module.app, ["clear"], input="n\n")

        assert result.exit_code != 0
        mock_inventory.clear_state.assert_not_called()
        assert "Inventory state has not been cleared" in result.output

    def test_failure(self, mocker, mock_inventory):
        """
        Test the clear command to ensure it handles exceptions raised by clear_state.
        """
        mock_inventory.clear_state = mocker.Mock(side_effect=Exception("beefed it"))

        result = runner.invoke(inventory_module.app, ["clear", "--force"])

        assert result.exit_code != 0
        assert "Error clearing inventory state" in result.output
        assert "beefed it" in result.output


class TestDiscoverCommand:
    """Tests for the discover command"""

    def test_success(self, mocker, mock_inventory):
        """
        Test the discover command success - run_task_with_progress returns no errors.
        """
        # Mock get_hosts_or_error to return a list of hosts
        mock_hosts = [mocker.Mock(name="host1"), mocker.Mock(name="host2")]
        mocker.patch.object(
            inventory_module, "get_hosts_or_error", return_value=mock_hosts
        )

        # Mock run_task_with_progress to return no errors (success case)
        mock_run_task = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=[]
        )

        result = runner.invoke(inventory_module.app, ["discover"])

        assert result.exit_code == 0

        # Verify run_task_with_progress was called with correct parameters
        mock_run_task.assert_called_once_with(
            inventory=mock_inventory,
            hosts=mock_hosts,
            task_name="discover",
            task_description="Gathering platform information",
            display_hosts=True,
            collect_errors=True,
            immediate_error_display=False,
        )

    def test_failure(self, mocker, mock_inventory):
        """
        Test the discover command failure - run_task_with_progress returns error tuples.
        """
        # Mock get_hosts_or_error to return a list of hosts
        mock_hosts = [mocker.Mock(name="host1"), mocker.Mock(name="host2")]
        mocker.patch.object(
            inventory_module, "get_hosts_or_error", return_value=mock_hosts
        )

        # Mock run_task_with_progress to return errors (failure case)
        errors = [
            ("host1", "Connection timeout"),
            ("host2", "Authentication failed"),
        ]
        mock_run_task = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=errors
        )

        result = runner.invoke(inventory_module.app, ["discover"])

        assert result.exit_code == 1  # Should exit with error code

        # Verify run_task_with_progress was called with correct parameters
        mock_run_task.assert_called_once_with(
            inventory=mock_inventory,
            hosts=mock_hosts,
            task_name="discover",
            task_description="Gathering platform information",
            display_hosts=True,
            collect_errors=True,
            immediate_error_display=False,
        )

        # Should display error messages
        assert (
            "The following hosts could not be discovered due to errors:"
            in result.output
        )
        assert "host1" in result.output
        assert "Connection timeout" in result.output
        assert "host2" in result.output
        assert "Authentication failed" in result.output

    def test_no_hosts(self, mocker, mock_inventory):
        """
        Test the discover command when get_hosts_or_error returns None.
        """
        mocker.patch.object(utils_module, "get_hosts_or_error", return_value=None)

        result = runner.invoke(inventory_module.app, ["discover"])

        assert result.exit_code == 0
        assert "No hosts found in inventory." in result.output

    @pytest.mark.parametrize(
        "cache_autosave,should_save",
        [
            (False, False),
            (True, True),
        ],
        ids=["disabled", "enabled"],
    )
    def test_autosave_behavior(
        self, mocker, mock_inventory, cache_autosave, should_save
    ):
        """
        Test the discover command autosave behavior based on configuration.
        """
        # Mock get_hosts_or_error to return a list of hosts
        mock_hosts = [mocker.Mock(name="host1")]
        mocker.patch.object(
            inventory_module, "get_hosts_or_error", return_value=mock_hosts
        )

        # Mock run_task_with_progress to return no errors
        mocker.patch.object(inventory_module, "run_task_with_progress", return_value=[])

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": cache_autosave}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        # Mock save function
        mock_save = mocker.patch.object(inventory_module, "save")

        result = runner.invoke(inventory_module.app, ["discover"])

        assert result.exit_code == 0

        # Check if save was called based on the should_save parameter
        if should_save:
            mock_save.assert_called_once()
        else:
            mock_save.assert_not_called()


class TestPingCommand:
    """Tests for the ping command."""

    @pytest.mark.parametrize(
        "hosts_data,run_task_results,expected_exit_code,command_args",
        [
            # All hosts online
            (
                ["host1", "host2"],
                [(True, None), (True, None)],
                0,
                [],
            ),
            # Partial failure - one host fails with exception
            (
                ["host1", "host2"],
                [(True, None), (False, Exception("Connection failed"))],
                1,
                [],
            ),
            # All hosts offline - single host fails without exception
            (
                ["host1"],
                [(False, None)],
                1,
                [],
            ),
            # Single host success with specific host argument
            (
                ["host1"],
                [(True, None)],
                0,
                ["host1"],
            ),
            # Mixed scenario - multiple hosts with failures
            (
                ["host1", "host2", "host3"],
                [(True, None), (False, None), (False, Exception("Timeout"))],
                1,
                [],
            ),
        ],
        ids=[
            "all_hosts_online",
            "partial_failure_with_exception",
            "all_hosts_offline",
            "specific_host_success",
            "mixed_results",
        ],
    )
    def test_ping_scenarios(
        self,
        mocker,
        mock_inventory,
        create_host,
        hosts_data,
        run_task_results,
        expected_exit_code,
        command_args,
    ):
        """Test various ping command scenarios."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )

        # Create hosts based on test data
        hosts = [create_host(name) for name in hosts_data]
        mock_get_hosts_or_error.return_value = hosts

        # Build run_task return value - combine host with result
        run_task_return = [
            (host, success, exception)
            for host, (success, exception) in zip(hosts, run_task_results)
        ]
        mock_inventory.run_task.return_value = run_task_return

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        # Build command arguments
        cmd_args = ["ping"] + command_args
        expected_get_hosts_args = command_args if command_args else None

        result = runner.invoke(inventory_module.app, cmd_args)

        assert result.exit_code == expected_exit_code
        mock_get_hosts_or_error.assert_called_once_with(expected_get_hosts_args)
        mock_inventory.run_task.assert_called_once_with("ping", hosts=hosts)

    def test_no_hosts(self, mocker, mock_inventory):
        """Test ping command when no hosts are found."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        mock_get_hosts_or_error.return_value = None

        result = runner.invoke(inventory_module.app, ["ping"])

        assert result.exit_code == 0  # Command completes successfully but does nothing
        mock_get_hosts_or_error.assert_called_once_with(None)
        mock_inventory.run_task.assert_not_called()

    @pytest.mark.parametrize(
        "autosave_enabled",
        [True, False],
        ids=["autosave_enabled", "autosave_disabled"],
    )
    def test_autosave_behavior(
        self, mocker, mock_inventory, create_host, autosave_enabled
    ):
        """Test ping command autosave behavior."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_inventory.run_task.return_value = [
            (host1, True, None),
        ]

        mock_save = mocker.patch.object(inventory_module, "save")

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": autosave_enabled}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        result = runner.invoke(inventory_module.app, ["ping"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)
        mock_inventory.run_task.assert_called_once_with("ping", hosts=[host1])

        if autosave_enabled:
            mock_save.assert_called_once()
        else:
            mock_save.assert_not_called()


class TestRefreshCommand:
    """Tests for the refresh command."""

    def test_basic_refresh(self, mocker, mock_inventory, create_host):
        """Test basic refresh command without options."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(inventory_module.app, ["refresh"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)

        # Should only call run_task_with_progress once for refresh_updates
        mock_run_task_with_progress.assert_called_once_with(
            inventory=mock_inventory,
            hosts=[host1],
            task_name="refresh_updates",
            task_description="Refreshing package updates",
            display_hosts=False,
            collect_errors=True,
            immediate_error_display=False,
        )

    def test_refresh_with_discover(self, mocker, mock_inventory, create_host):
        """Test refresh command with --discover option."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(inventory_module.app, ["refresh", "--discover"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)

        # Should call run_task_with_progress twice: discover + refresh_updates
        assert mock_run_task_with_progress.call_count == 2

        # Check first call (discover)
        first_call = mock_run_task_with_progress.call_args_list[0]
        assert first_call.kwargs["task_name"] == "discover"
        assert first_call.kwargs["task_description"] == "Gathering platform information"

        # Check second call (refresh_updates)
        second_call = mock_run_task_with_progress.call_args_list[1]
        assert second_call.kwargs["task_name"] == "refresh_updates"
        assert second_call.kwargs["task_description"] == "Refreshing package updates"

    def test_refresh_with_sync(self, mocker, mock_inventory, create_host):
        """Test refresh command with --sync option."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(inventory_module.app, ["refresh", "--sync"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)

        # Should call run_task_with_progress twice: sync_repos + refresh_updates
        assert mock_run_task_with_progress.call_count == 2

        # Check first call (sync_repos)
        first_call = mock_run_task_with_progress.call_args_list[0]
        assert first_call.kwargs["task_name"] == "sync_repos"
        assert first_call.kwargs["task_description"] == "Syncing package repositories"

        # Check second call (refresh_updates)
        second_call = mock_run_task_with_progress.call_args_list[1]
        assert second_call.kwargs["task_name"] == "refresh_updates"
        assert second_call.kwargs["task_description"] == "Refreshing package updates"

    def test_refresh_with_all_options(self, mocker, mock_inventory, create_host):
        """Test refresh command with both --discover and --sync options."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(
            inventory_module.app, ["refresh", "--discover", "--sync"]
        )

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)

        # Should call run_task_with_progress three times: discover + sync_repos + refresh_updates
        assert mock_run_task_with_progress.call_count == 3

        # Check all three calls
        calls = mock_run_task_with_progress.call_args_list
        assert calls[0].kwargs["task_name"] == "discover"
        assert calls[1].kwargs["task_name"] == "sync_repos"
        assert calls[2].kwargs["task_name"] == "refresh_updates"

    def test_refresh_with_errors(self, mocker, mock_inventory, create_host):
        """Test refresh command when errors occur."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        host2 = create_host("host2")
        mock_get_hosts_or_error.return_value = [host1, host2]

        # Mock run_task_with_progress to return errors
        errors = [("host1", "Update failed"), ("host2", "Network timeout")]
        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=errors
        )

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(inventory_module.app, ["refresh"])

        assert result.exit_code == 1  # Should exit with error code
        mock_get_hosts_or_error.assert_called_once_with(None)
        mock_run_task_with_progress.assert_called_once()

        # Should display error messages
        assert "host1" in result.output
        assert "Update failed" in result.output
        assert "host2" in result.output
        assert "Network timeout" in result.output

    def test_refresh_with_specific_hosts(self, mocker, mock_inventory, create_host):
        """Test refresh command with specific host names."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_app_config = mocker.patch.object(inventory_module, "app_config")
        mock_app_config.__getitem__.return_value = {"cache_autosave": False}

        result = runner.invoke(inventory_module.app, ["refresh", "host1", "host2"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(["host1", "host2"])
        mock_run_task_with_progress.assert_called_once()

    def test_refresh_no_hosts(self, mocker, mock_inventory):
        """Test refresh command when no hosts are found."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        mock_get_hosts_or_error.return_value = None

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )

        result = runner.invoke(inventory_module.app, ["refresh"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)
        mock_run_task_with_progress.assert_not_called()

    @pytest.mark.parametrize(
        "autosave_enabled",
        [True, False],
        ids=["enabled", "disabled"],
    )
    def test_refresh_autosave_behavior(
        self, mocker, mock_inventory, create_host, autosave_enabled
    ):
        """Test refresh command autosave behavior."""
        mock_get_hosts_or_error = mocker.patch.object(
            inventory_module, "get_hosts_or_error"
        )
        host1 = create_host("host1")
        mock_get_hosts_or_error.return_value = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_save = mocker.patch.object(inventory_module, "save")

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": autosave_enabled}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        result = runner.invoke(inventory_module.app, ["refresh"])

        assert result.exit_code == 0
        mock_get_hosts_or_error.assert_called_once_with(None)
        mock_run_task_with_progress.assert_called_once()

        if autosave_enabled:
            mock_save.assert_called_once()
        else:
            mock_save.assert_not_called()
