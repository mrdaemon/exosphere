import pytest

from exosphere.commands import inventory as inventory_module
from exosphere.commands import utils as utils_module
from exosphere.config import Configuration
from exosphere.objects import HostOperation


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the inventory command module."""
    patch_console(inventory_module)


@pytest.fixture(autouse=True)
def mock_inventory(mocker, wire_get_host):
    """
    Patch context inventory for all tests.

    The fake inventory resolves host names off its own ``hosts`` list (so the
    HostArg converter works for commands invoked with specific names) and
    delegates filtering/sorting to the real implementations so the status
    command returns actual host lists rather than bare Mocks.
    """
    fake_inventory = mocker.create_autospec(inventory_module.Inventory, instance=True)
    fake_inventory.hosts = []

    # Resolve names off the current hosts list so the HostArg converter
    # (which calls get_host) works for commands invoked with explicit names.
    wire_get_host(fake_inventory)

    real = inventory_module.Inventory
    fake_inventory.filter_hosts.side_effect = lambda mode, hosts=None: (
        real.filter_hosts(fake_inventory, mode, hosts)
    )
    fake_inventory.sort_hosts.side_effect = lambda by, hosts=None, reverse=False: (
        real.sort_hosts(fake_inventory, by, hosts, reverse)
    )

    mocker.patch.object(utils_module.context, "inventory", fake_inventory)
    return fake_inventory


@pytest.fixture
def create_host(make_host):
    """
    Factory fixture to create Host autospec mocks with default values.

    Thin wrapper over the shared ``make_host`` factory that supplies this
    module's domain defaults (a discovered Debian 12 host).
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
        supported=True,
        description=None,
        needs_reboot=None,
    ):
        return make_host(
            name,
            os=os,
            flavor=flavor,
            version=version,
            updates=updates if updates is not None else [],
            security_updates=security_updates if security_updates is not None else [],
            online=online,
            is_stale=is_stale,
            supported=supported,
            description=description,
            needs_reboot=needs_reboot,
        )

    return _create_host


class TestStatusCommand:
    """Tests for the status command"""

    def test_shows_table(self, create_host, mock_inventory, capsys):
        """
        Basic test for the status command to ensure it shows a table with host information.
        This is meant to be a somewhat comprehensive catch-all as first test.
        """
        host = create_host(name="host1", updates=[1, 2, 3, 4], security_updates=[1])

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Host Status Overview" in out
        assert "host1" in out
        assert "linux" in out
        assert "debian" in out
        assert "12" in out
        assert "4" in out
        assert "1" in out
        assert "4 *" not in out  # No stale hosts
        assert "1 *" not in out  # No stale hosts
        assert "Online" in out
        assert "Offline" not in out

    def test_with_stale_hosts(self, create_host, mock_inventory, capsys):
        """
        Test the status command to ensure it correctly identifies stale hosts.
        """
        host = create_host(
            name="host1", updates=[1, 2, 3, 4], security_updates=[1], is_stale=True
        )

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "4 *" in out  # Stale hosts marked with *
        assert "1 *" in out  # Stale hosts marked with *

    def test_with_pending_reboot(self, create_host, mock_inventory, capsys):
        """
        A host pending a reboot is flagged with a '!' marker in the status table.
        """
        host = create_host(name="host1", needs_reboot=True)
        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "!" in out

    def test_no_hosts(self, mock_inventory, capsys):
        """
        Test the status command with an empty inventory.

        get_hosts_or_all returns None for an empty inventory, so the command
        exits with an input error (exit 1).
        """
        mock_inventory.hosts = []

        code = inventory_module.app(["status"], result_action="return_value")

        assert code == 1
        assert "No hosts found in inventory." in capsys.readouterr().err

    def test_with_specific_hosts(self, create_host, mock_inventory, capsys):
        """
        Test the status command with specific host names.
        """
        host1 = create_host(name="host1", updates=[1, 2, 3], security_updates=[1])
        host2 = create_host(name="host2", updates=[1, 2], security_updates=[])

        # Mock inventory.hosts to contain the hosts
        mock_inventory.hosts = [host1, host2]

        code = inventory_module.app(["status", "host1"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Host Status Overview" in out
        assert "host1" in out
        assert "host2" not in out  # Should not show host2

    def test_with_no_updates(self, create_host, mock_inventory, capsys):
        """
        Test the status command with a host that has no updates.
        """
        host = create_host(name="host1", updates=[], security_updates=[])

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "host1" in out
        assert out.count("0") == 2  # Should show 0 updates and security updates

    def test_with_security_updates(self, create_host, mock_inventory, capsys):
        """
        Test the status command displays security updates in red when present.
        """
        host = create_host(name="host1", updates=[1, 2, 3], security_updates=[1, 2])

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "2" in out  # Should show security update count

    def test_with_offline_host(self, create_host, mock_inventory, capsys):
        """
        Test the status command with an offline host.
        """
        host = create_host(
            name="host1", updates=[1, 2, 3], security_updates=[], online=False
        )

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Offline" in out

    def test_with_undiscovered_host(self, create_host, mock_inventory, capsys):
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

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "host1" in out
        assert "(undiscovered)" in out
        assert out.count("(undiscovered)") == 3

        assert out.count("—") == 2  # No data for updates
        assert out.count("*") == 1  # No stale, except legend

    def test_with_unsupported_host(self, create_host, mock_inventory, capsys):
        """
        Test the status command with unsupported hosts
        """
        host = create_host(
            name="host8",
            os="exotic-os",
            flavor=None,
            version=None,
            updates=[],
            security_updates=[],
            online=True,
            supported=False,
        )

        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "host8" in out
        assert "exotic-os" in out
        assert "(unsupport" in out  # Truncated ; codespell:ignore unsupport
        assert out.count("(unsupport") == 2  # codespell:ignore unsupport
        assert out.count("—") == 2

    @pytest.mark.parametrize("flag", ["--full", "-f"], ids=["long", "short"])
    def test_full_shows_description_column(
        self, create_host, mock_inventory, flag, capsys
    ):
        """
        Test that --full adds a Description column with the host description.
        """
        # Create a host with a description one without
        host1 = create_host(name="host1", description="primary web server")
        host2 = create_host(name="host2", description=None)
        mock_inventory.hosts = [host1, host2]

        code = inventory_module.app(["status", flag], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Description" in out  # Column present
        assert "primary web server" in out  # one description
        assert out.count("—") == 1  # one placeholder

    def test_description_hidden_without_full(self, create_host, mock_inventory, capsys):
        """
        Test that the description column is not shown without --full.
        """
        host = create_host(name="host1", description="primary web server")
        mock_inventory.hosts = [host]

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Description" not in out
        assert "primary web server" not in out

    def test_multiple_hosts_with_different_states(
        self, create_host, mock_inventory, capsys
    ):
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

        # Unsupported host
        host4 = create_host(
            name="server4",
            os="exotic-os",
            flavor=None,
            version=None,
            updates=[],
            security_updates=[],
            online=True,
            supported=False,
        )
        hosts.append(host4)

        mock_inventory.hosts = hosts

        code = inventory_module.app(["status"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "server1" in out
        assert "server2" in out
        assert "server3" in out
        assert "ubuntu" in out
        assert "centos" in out
        assert "exotic-os" in out
        assert out.count("Online") == 3
        assert out.count("Offline") == 1
        assert "2 *" in out  # Stale updates for server2
        assert out.count("—") == 2  # Unsupported update counts

    @pytest.mark.parametrize(
        "flag",
        ["--updates-only", "-u"],
        ids=["long", "short"],
    )
    def test_updates_only_filter(self, create_host, mock_inventory, flag, capsys):
        """
        Test status command with --updates-only flag filters out hosts without updates.
        """
        host_with_updates = create_host(
            name="host1", updates=[1, 2, 3], security_updates=[1]
        )
        host_without_updates = create_host(
            name="host2", updates=[], security_updates=[]
        )

        mock_inventory.hosts = [host_with_updates, host_without_updates]

        code = inventory_module.app(["status", flag], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "host1" in out
        assert "host2" not in out
        assert "Host Status (updates only)" in out

    @pytest.mark.parametrize(
        "flag",
        ["--security-only", "-s"],
        ids=["long", "short"],
    )
    def test_security_only_filter(self, create_host, mock_inventory, flag, capsys):
        """
        Test status command with --security-only flag filters to only hosts with security updates.
        """
        host_with_security = create_host(
            name="host1", updates=[1, 2, 3], security_updates=[1, 2]
        )
        host_without_security = create_host(
            name="host2", updates=[1, 2], security_updates=[]
        )
        host_no_updates = create_host(name="host3", updates=[], security_updates=[])

        mock_inventory.hosts = [
            host_with_security,
            host_without_security,
            host_no_updates,
        ]

        code = inventory_module.app(["status", flag], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "host1" in out
        assert "host2" not in out
        assert "host3" not in out
        assert "Host Status (security updates only)" in out

    def test_both_filters_mutually_exclusive(self, create_host, mock_inventory, capsys):
        """
        --updates-only and --security-only are mutually exclusive; supplying
        both is rejected as an input error by the Filtering Options validator.
        """
        mock_inventory.hosts = [
            create_host(name="host1", updates=[1, 2, 3], security_updates=[1])
        ]

        with pytest.raises(SystemExit) as exc_info:
            inventory_module.app(["status", "--updates-only", "--security-only"])

        assert exc_info.value.code == 1
        assert "Mutually exclusive arguments" in capsys.readouterr().err

    def test_no_hosts_matching_criteria(self, create_host, mock_inventory, capsys):
        """
        Test status command when filters result in no matching hosts.
        Should show a message and exit with code 3.
        """
        host_no_updates = create_host(name="host1", updates=[], security_updates=[])

        mock_inventory.hosts = [host_no_updates]

        code = inventory_module.app(
            ["status", "--updates-only"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 3
        assert "No hosts matching requested criteria" in out
        assert "host1" not in out

    def test_filters_with_specific_host_names(
        self, create_host, mock_inventory, capsys
    ):
        """
        Test status command with filters combined with specific host names.
        """
        host1_with_updates = create_host(
            name="host1", updates=[1, 2, 3], security_updates=[1]
        )
        host2_without_updates = create_host(
            name="host2", updates=[], security_updates=[]
        )
        host3_with_updates = create_host(name="host3", updates=[1], security_updates=[])

        mock_inventory.hosts = [
            host1_with_updates,
            host2_without_updates,
            host3_with_updates,
        ]

        code = inventory_module.app(
            ["status", "--updates-only", "host1", "host2"],
            result_action="return_value",
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "host1" in out
        assert "host2" not in out
        assert "host3" not in out

    def test_sort_by_host(self, create_host, mock_inventory, capsys):
        """
        Test status command with --sort host orders rows alphabetically.
        """
        mock_inventory.hosts = [
            create_host(name="charlie"),
            create_host(name="alpha"),
            create_host(name="bravo"),
        ]

        code = inventory_module.app(
            ["status", "--sort", "host"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert out.index("alpha") < out.index("bravo") < out.index("charlie")

    def test_sort_reverse(self, create_host, mock_inventory, capsys):
        """
        Test status command with --sort host --reverse orders rows descending.
        """
        mock_inventory.hosts = [
            create_host(name="alpha"),
            create_host(name="bravo"),
            create_host(name="charlie"),
        ]

        code = inventory_module.app(
            ["status", "--sort", "host", "--reverse"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert out.index("charlie") < out.index("bravo") < out.index("alpha")

    def test_sort_invalid_field_errors(self, create_host, mock_inventory):
        """
        Test status command with an invalid --sort value is rejected.

        An invalid enum value is a coercion (input) error raised during
        argument binding.
        """
        mock_inventory.hosts = [create_host(name="host1")]

        with pytest.raises(SystemExit) as exc_info:
            inventory_module.app(["status", "--sort", "bogus"])

        assert exc_info.value.code != 0

    def test_reverse_without_sort_errors(self, create_host, mock_inventory, capsys):
        """
        Test --reverse without --sort is rejected by the validation
        """
        mock_inventory.hosts = [
            create_host(name="bravo"),
            create_host(name="alpha"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            inventory_module.app(["status", "--reverse"])

        assert exc_info.value.code == 1
        assert "--reverse requires --sort" in capsys.readouterr().err


class TestSaveCommand:
    """Tests for the save command"""

    @pytest.fixture(autouse=True)
    def _interactive(self, mocker):
        """Patch context to simulate interactive mode being used"""
        mocker.patch.object(utils_module.context, "interactive", True)

    def test_success(self, mocker, mock_inventory):
        """
        Test the save command to ensure it calls the save_state method on the inventory.
        """
        mock_inventory.save_state = mocker.Mock()

        code = inventory_module.app(["save"], result_action="return_value")

        assert code is None  # save returns None on success
        mock_inventory.save_state.assert_called_once()

    def test_failure(self, mocker, mock_inventory, capsys):
        """
        Test the save command to ensure it handles exceptions raised by save_state.
        """
        mock_inventory.save_state = mocker.Mock(
            side_effect=Exception("Some write problem")
        )

        with pytest.raises(SystemExit) as exc_info:
            inventory_module.app(["save"])

        out = capsys.readouterr().out
        assert exc_info.value.code == 2  # Application error
        assert "Error saving inventory state" in out
        assert "Some write problem" in out

    def test_bails_outside_interactive(self, mocker, mock_inventory, capsys):
        """save refuses to run from a one-shot CLI invocation."""
        mocker.patch.object(utils_module.context, "interactive", False)

        with pytest.raises(SystemExit) as exc_info:
            inventory_module.app(["save"])

        assert exc_info.value.code == 2  # Application error: wrong context
        assert "only available in Interactive Mode" in capsys.readouterr().err


class TestClearCommand:
    """Tests for the clear command"""

    @pytest.fixture(autouse=True)
    def _tty(self, mocker):
        """clear's confirmation assumes a human at a terminal by default."""
        mocker.patch("sys.stdin.isatty", return_value=True)

    def test_no_tty_without_force(self, mocker, mock_inventory, capsys):
        """Non-TTY without --force refuses, hints at --force, and never prompts."""
        mocker.patch("sys.stdin.isatty", return_value=False)
        ask = mocker.patch("exosphere.commands.inventory.Confirm.ask")
        mock_inventory.clear_state = mocker.Mock()

        code = inventory_module.app(["clear"], result_action="return_value")

        assert code == 1
        assert not ask.called
        mock_inventory.clear_state.assert_not_called()
        assert "not a tty" in capsys.readouterr().err.casefold()

    def test_force_clears_without_tty(self, mocker, mock_inventory):
        """--force clears without prompting, even when not a TTY."""
        mocker.patch("sys.stdin.isatty", return_value=False)
        ask = mocker.patch("exosphere.commands.inventory.Confirm.ask")
        mock_inventory.clear_state = mocker.Mock()

        code = inventory_module.app(["clear", "--force"], result_action="return_value")

        assert code == 0
        assert not ask.called
        mock_inventory.clear_state.assert_called_once()

    def test_success(self, mocker, mock_inventory, capsys):
        """
        Test the clear command to ensure it clears the inventory.
        """
        mock_clear = mock_inventory.clear_state = mocker.Mock()

        code = inventory_module.app(["clear", "--force"], result_action="return_value")

        assert code == 0
        mock_clear.assert_called_once()
        assert "Inventory state has been cleared" in capsys.readouterr().out

    def test_no_force(self, mocker, mock_inventory):
        """
        Test the clear command prompts for confirmation when --force is not used.
        """
        mock_ask = mocker.patch(
            "exosphere.commands.inventory.Confirm.ask", return_value=False
        )

        code = inventory_module.app(["clear"], result_action="return_value")

        assert code == 1  # Input error: not confirmed
        mock_ask.assert_called_once()

    def test_confirmation(self, mocker, mock_inventory, capsys):
        """
        Test the clear command clears the inventory when confirmed.
        """
        mocker.patch("exosphere.commands.inventory.Confirm.ask", return_value=True)
        mock_inventory.clear_state = mocker.Mock()

        code = inventory_module.app(["clear"], result_action="return_value")

        assert code == 0
        mock_inventory.clear_state.assert_called_once()
        assert "Inventory state has been cleared" in capsys.readouterr().out

    def test_cancelled(self, mocker, mock_inventory, capsys):
        """
        Test the clear command does not clear the inventory when cancelled.
        """
        mocker.patch("exosphere.commands.inventory.Confirm.ask", return_value=False)
        mock_inventory.clear_state = mocker.Mock()

        code = inventory_module.app(["clear"], result_action="return_value")

        assert code == 1
        mock_inventory.clear_state.assert_not_called()
        assert "Inventory state has not been cleared" in capsys.readouterr().out

    def test_failure(self, mocker, mock_inventory, capsys):
        """
        Test the clear command handles exceptions raised by clear_state.
        """
        mock_inventory.clear_state = mocker.Mock(side_effect=Exception("beefed it"))

        code = inventory_module.app(["clear", "--force"], result_action="return_value")

        err = capsys.readouterr().err
        assert code == 2  # Application error
        assert "Error clearing inventory state" in err
        assert "beefed it" in err


class TestDiscoverCommand:
    """Tests for the discover command"""

    def test_success(self, mocker, mock_inventory):
        """
        Test the discover command success - run_task_with_progress returns no errors.
        """
        mock_hosts = [mocker.Mock(name="host1"), mocker.Mock(name="host2")]
        mock_inventory.hosts = mock_hosts

        # Mock run_task_with_progress to return no errors (success case)
        mock_run_task = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=[]
        )

        code = inventory_module.app(["discover"], result_action="return_value")

        assert code == 0

        # Verify run_task_with_progress was called with correct parameters
        mock_run_task.assert_called_once_with(
            inventory=mock_inventory,
            hosts=mock_hosts,
            operation=HostOperation.DISCOVER,
            task_description="Gathering platform information",
            display_hosts=True,
            collect_errors=True,
            immediate_error_display=False,
        )

    def test_failure(self, mocker, mock_inventory, capsys):
        """
        Test the discover command failure - run_task_with_progress returns error tuples.
        """
        mock_hosts = [mocker.Mock(name="host1"), mocker.Mock(name="host2")]
        mock_inventory.hosts = mock_hosts

        # Mock run_task_with_progress to return errors (failure case)
        errors = [
            ("host1", "Connection timeout"),
            ("host2", "Authentication failed"),
        ]
        mock_run_task = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=errors
        )

        code = inventory_module.app(["discover"], result_action="return_value")

        assert code == 2  # Application error

        # Verify run_task_with_progress was called with correct parameters
        mock_run_task.assert_called_once_with(
            inventory=mock_inventory,
            hosts=mock_hosts,
            operation=HostOperation.DISCOVER,
            task_description="Gathering platform information",
            display_hosts=True,
            collect_errors=True,
            immediate_error_display=False,
        )

        # Should display error messages
        out = capsys.readouterr().out
        assert "The following hosts could not be discovered due to errors:" in out
        assert "host1" in out
        assert "Connection timeout" in out
        assert "host2" in out
        assert "Authentication failed" in out

    def test_no_hosts(self, mock_inventory, capsys):
        """
        Test the discover command with an empty inventory.
        """
        mock_inventory.hosts = []

        code = inventory_module.app(["discover"], result_action="return_value")

        assert code == 1  # Input error: no hosts
        assert "No hosts found in inventory." in capsys.readouterr().err

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
        mock_inventory.hosts = [mocker.Mock(name="host1")]

        # Mock run_task_with_progress to return no errors
        mocker.patch.object(inventory_module, "run_task_with_progress", return_value=[])

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": cache_autosave}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        # Mock save function
        mock_save = mocker.patch.object(inventory_module, "save_inventory_state")

        code = inventory_module.app(["discover"], result_action="return_value")

        assert code == 0

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
                2,
                [],
            ),
            # All hosts offline - single host fails without exception
            (
                ["host1"],
                [(False, None)],
                2,
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
                2,
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
        # Create hosts based on test data and expose them on the inventory so
        # the HostArg converter can resolve any explicit names.
        hosts = [create_host(name) for name in hosts_data]
        mock_inventory.hosts = hosts

        # Build run_task return value - combine host with result
        run_task_return = [
            (host, success, exception)
            for host, (success, exception) in zip(hosts, run_task_results)
        ]
        mock_inventory.run_task.return_value = run_task_return

        # Disable autosave to keep the test focused
        test_config = Configuration()
        test_config.update_from_mapping({"options": {"cache_autosave": False}})
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(
            ["ping"] + command_args, result_action="return_value"
        )

        assert code == expected_exit_code
        mock_inventory.run_task.assert_called_once_with(HostOperation.PING, hosts=hosts)

    def test_no_hosts(self, mock_inventory, capsys):
        """Test ping command with an empty inventory."""
        mock_inventory.hosts = []

        code = inventory_module.app(["ping"], result_action="return_value")

        assert code == 1  # Input error: no hosts
        assert "No hosts found in inventory." in capsys.readouterr().err
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
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_inventory.run_task.return_value = [
            (host1, True, None),
        ]

        mock_save = mocker.patch.object(inventory_module, "save_inventory_state")

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": autosave_enabled}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(["ping"], result_action="return_value")

        assert code == 0
        mock_inventory.run_task.assert_called_once_with(
            HostOperation.PING, hosts=[host1]
        )

        if autosave_enabled:
            mock_save.assert_called_once()
        else:
            mock_save.assert_not_called()


class TestRefreshCommand:
    """Tests for the refresh command."""

    def test_basic_refresh(self, mocker, mock_inventory, create_host):
        """Test basic refresh command without options."""
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(["refresh"], result_action="return_value")

        assert code == 0

        # Should only call run_task_with_progress once for refresh_updates
        mock_run_task_with_progress.assert_called_once_with(
            inventory=mock_inventory,
            hosts=[host1],
            operation=HostOperation.REFRESH,
            task_description="Refreshing package updates",
            display_hosts=False,
            collect_errors=True,
            immediate_error_display=False,
        )

    def test_refresh_with_discover(self, mocker, mock_inventory, create_host):
        """Test refresh command with --discover option."""
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(
            ["refresh", "--discover"], result_action="return_value"
        )

        assert code == 0

        # Should call run_task_with_progress twice: discover + refresh_updates
        assert mock_run_task_with_progress.call_count == 2

        # Check first call (discover)
        first_call = mock_run_task_with_progress.call_args_list[0]
        assert first_call.kwargs["operation"] is HostOperation.DISCOVER
        assert first_call.kwargs["task_description"] == "Gathering platform information"

        # Check second call (refresh_updates)
        second_call = mock_run_task_with_progress.call_args_list[1]
        assert second_call.kwargs["operation"] is HostOperation.REFRESH
        assert second_call.kwargs["task_description"] == "Refreshing package updates"

    def test_refresh_with_sync(self, mocker, mock_inventory, create_host):
        """Test refresh command with --sync option."""
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(["refresh", "--sync"], result_action="return_value")

        assert code == 0

        # Should call run_task_with_progress twice: sync_repos + refresh_updates
        assert mock_run_task_with_progress.call_count == 2

        # Check first call (sync_repos)
        first_call = mock_run_task_with_progress.call_args_list[0]
        assert first_call.kwargs["operation"] is HostOperation.SYNC
        assert first_call.kwargs["task_description"] == "Syncing package repositories"

        # Check second call (refresh_updates)
        second_call = mock_run_task_with_progress.call_args_list[1]
        assert second_call.kwargs["operation"] is HostOperation.REFRESH
        assert second_call.kwargs["task_description"] == "Refreshing package updates"

    def test_refresh_with_all_options(self, mocker, mock_inventory, create_host):
        """Test refresh command with both --discover and --sync options."""
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(
            ["refresh", "--discover", "--sync"], result_action="return_value"
        )

        assert code == 0

        # Should call run_task_with_progress three times: discover + sync_repos + refresh_updates
        assert mock_run_task_with_progress.call_count == 3

        # Check all three calls
        calls = mock_run_task_with_progress.call_args_list
        assert calls[0].kwargs["operation"] is HostOperation.DISCOVER
        assert calls[1].kwargs["operation"] is HostOperation.SYNC
        assert calls[2].kwargs["operation"] is HostOperation.REFRESH

    def test_refresh_with_errors(self, mocker, mock_inventory, create_host, capsys):
        """Test refresh command when errors occur."""
        host1 = create_host("host1")
        host2 = create_host("host2")
        mock_inventory.hosts = [host1, host2]

        # Mock run_task_with_progress to return errors
        errors = [("host1", "Update failed"), ("host2", "Network timeout")]
        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress", return_value=errors
        )

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(["refresh"], result_action="return_value")

        assert code == 2  # Application error
        mock_run_task_with_progress.assert_called_once()

        # Should display error messages
        out = capsys.readouterr().out
        assert "host1" in out
        assert "Update failed" in out
        assert "host2" in out
        assert "Network timeout" in out

    def test_refresh_with_specific_hosts(self, mocker, mock_inventory, create_host):
        """Test refresh command with specific host names."""
        host1 = create_host("host1")
        host2 = create_host("host2")
        mock_inventory.hosts = [host1, host2]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        config = {"options": {"cache_autosave": False}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(
            ["refresh", "host1", "host2"], result_action="return_value"
        )

        assert code == 0
        mock_run_task_with_progress.assert_called_once()
        assert mock_run_task_with_progress.call_args.kwargs["hosts"] == [host1, host2]

    def test_refresh_no_hosts(self, mock_inventory, capsys):
        """Test refresh command with an empty inventory."""
        mock_inventory.hosts = []

        code = inventory_module.app(["refresh"], result_action="return_value")

        assert code == 1  # Input error: no hosts
        assert "No hosts found in inventory." in capsys.readouterr().err

    @pytest.mark.parametrize(
        "autosave_enabled",
        [True, False],
        ids=["enabled", "disabled"],
    )
    def test_refresh_autosave_behavior(
        self, mocker, mock_inventory, create_host, autosave_enabled
    ):
        """Test refresh command autosave behavior."""
        host1 = create_host("host1")
        mock_inventory.hosts = [host1]

        mock_run_task_with_progress = mocker.patch.object(
            inventory_module, "run_task_with_progress"
        )
        mock_run_task_with_progress.return_value = []  # No errors

        mock_save = mocker.patch.object(inventory_module, "save_inventory_state")

        # Mock app_config with the specified autosave setting
        config = {"options": {"cache_autosave": autosave_enabled}}
        test_config = Configuration()
        test_config.update_from_mapping(config)
        mocker.patch.object(inventory_module, "app_config", test_config)

        code = inventory_module.app(["refresh"], result_action="return_value")

        assert code == 0
        mock_run_task_with_progress.assert_called_once()

        if autosave_enabled:
            mock_save.assert_called_once()
        else:
            mock_save.assert_not_called()
