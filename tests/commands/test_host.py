import pytest

from exosphere.commands import host as host_module
from exosphere.commands import utils as utils_module
from exosphere.data import Update


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the host command module."""
    patch_console(host_module)


@pytest.fixture
def mock_host(mocker):
    """
    Create a mock Host object with predefined attributes and methods.
    This is a crappy non-exhaustive fixture but it's all we need.
    """
    MockHost = mocker.patch("exosphere.objects.Host", autospec=True)
    instance = MockHost.return_value
    instance.name = "testhost"
    instance.ip = "127.0.0.1"
    instance.port = 22
    instance.description = "Mock Host"
    instance.online = True
    instance.supported = True
    instance.is_stale = False
    instance.flavor = "ubuntu"
    instance.os = "ubuntu"
    instance.version = "22.04"
    instance.package_manager = "apt"
    instance.last_refresh = None

    instance.updates = [
        Update(
            name="bash",
            current_version="5.0",
            new_version="5.1",
            security=False,
            source="main",
        ),
        Update(
            name="openssl",
            current_version="1.1.1",
            new_version="1.1.2",
            security=True,
            source="security",
        ),
    ]
    instance.security_updates = [instance.updates[1]]

    # We store the run state of methods via stupid
    # attributes so we can check if they were created.
    # This saves us from having to generate mocks for each
    # and doing assertions on them.
    def discover():
        instance.discovered = True

    def sync_repos():
        instance.repos_synced = True

    def refresh_updates():
        instance.updates_refreshed = True

    def ping(close_connection=True):
        return instance.online

    instance.discover.side_effect = discover
    instance.sync_repos.side_effect = sync_repos
    instance.refresh_updates.side_effect = refresh_updates
    instance.ping.side_effect = ping

    return instance


@pytest.fixture
def fake_inventory(mock_host):
    """The vaguest simulacrum of an inventory"""

    class FakeInventory:
        hosts = [mock_host]

        def get_host(self, name):
            if name == mock_host.name:
                return mock_host
            return None

    return FakeInventory()


@pytest.fixture(autouse=True)
def patch_context_inventory(mocker, fake_inventory):
    """
    Patch the context's inventory to use our fake inventory.
    """
    mocker.patch.object(utils_module.context, "inventory", fake_inventory)


@pytest.fixture(autouse=True)
def patch_save_inventory(mocker):
    """
    Patch out the save_inventory_state function to, well, not.
    """
    mocker.patch.object(host_module, "save_inventory_state")


class TestShowCommand:
    """Tests for the 'host show' command."""

    def test_basic_info(self, mock_host):
        """
        Test showing a host with basic information.
        """
        code = host_module.app(["show", mock_host.name], result_action="return_value")
        assert code == 0

    def test_with_updates(self, mock_host):
        """
        Test showing a host with updates information.
        """
        code = host_module.app(
            ["show", mock_host.name, "--updates"], result_action="return_value"
        )
        assert code == 0

    def test_with_security_only(self, mock_host):
        """
        Test showing a host with security updates only.
        """
        code = host_module.app(
            ["show", mock_host.name, "--updates", "--security-only"],
            result_action="return_value",
        )
        assert code == 0

    def test_host_not_found(self, mock_host):
        """
        Test showing a host that does not exist in the inventory.

        The host argument is resolved by a converter, so an unknown name is
        an input error (exit 1) raised during argument binding.
        """
        with pytest.raises(SystemExit) as exc_info:
            host_module.app(["show", "not_test_host"])

        assert exc_info.value.code == 1
        assert not hasattr(mock_host, "discovered")

    def test_with_last_refresh_date(self, mock_host, capsys):
        """
        Test showing a host with a last refresh date displayed.
        """
        from datetime import datetime, timezone

        # Set a UTC datetime on the mock host
        utc_time = datetime(2025, 7, 22, 14, 30, 45, tzinfo=timezone.utc)
        mock_host.last_refresh = utc_time

        code = host_module.app(["show", mock_host.name], result_action="return_value")

        assert code == 0

        # Output should display local time
        expected_local = utc_time.astimezone().strftime("%a %b %d %H:%M:%S %Y")
        assert expected_local in capsys.readouterr().out

    def test_security_only_without_updates_flag(self, mock_host, capsys):
        """
        Test showing security-only updates when --no-updates is specified.
        """
        code = host_module.app(
            ["show", mock_host.name, "--no-updates", "--security-only"],
            result_action="return_value",
        )

        assert code == 1  # Input error
        assert (
            "Error: --security-only option is only valid with --updates"
            in capsys.readouterr().err
        )

    def test_no_updates_available(self, mock_host, capsys):
        """
        Test host show with no updates available.
        """
        # Clear all updates from the mock host
        mock_host.updates = []
        mock_host.security_updates = []

        code = host_module.app(
            ["show", mock_host.name, "--updates"], result_action="return_value"
        )

        assert code == 0
        assert "No updates available for this host." in capsys.readouterr().out

    def test_unsupported_host_display(self, mock_host, capsys):
        """
        Test host show with an unsupported host.
        """
        # Mark host as unsupported but online
        mock_host.supported = False
        mock_host.online = True
        mock_host.os = "irix"
        mock_host.flavor = None
        mock_host.version = None
        mock_host.package_manager = None

        code = host_module.app(["show", mock_host.name], result_action="return_value")

        assert code == 0
        assert "irix (Unsupported OS)" in capsys.readouterr().out

    def test_unsupported_host_no_updates_display(self, mock_host, capsys):
        """
        Test that updates are not shown for unsupported hosts.
        """
        # Mark host as unsupported
        mock_host.supported = False
        mock_host.online = True
        mock_host.os = "Darwin"

        code = host_module.app(
            ["show", mock_host.name, "--updates"], result_action="return_value"
        )

        assert code == 0
        assert (
            "Update info is not available for unsupported hosts."
            in capsys.readouterr().err
        )


class TestDiscoverCommand:
    """Tests for the 'host discover' command."""

    def test_basic_discovery(self, mock_host):
        """
        Test discovering a host that exists in the inventory.
        """
        code = host_module.app(
            ["discover", mock_host.name], result_action="return_value"
        )

        assert code == 0
        assert hasattr(mock_host, "discovered")

    def test_host_not_found(self, mock_host):
        """
        Test discovering a host that does not exist in the inventory.
        """
        with pytest.raises(SystemExit) as exc_info:
            host_module.app(["discover", "not_test_host"])

        assert exc_info.value.code == 1  # Input error from converter
        assert not hasattr(mock_host, "discovered")

    def test_with_exception(self, mock_host, capsys):
        """
        Test discovering a host when host.discover() raises an exception.
        """
        # Make discover() raise an exception
        mock_host.discover.side_effect = Exception("Connection failed")

        code = host_module.app(
            ["discover", mock_host.name], result_action="return_value"
        )

        assert code == 2  # Application error
        assert "Connection failed" in capsys.readouterr().out


class TestRefreshCommand:
    """Tests for the 'host refresh' command."""

    def test_basic_refresh(self, mock_host):
        """
        Test refreshing a host's updates without full sync
        """
        code = host_module.app(
            ["refresh", mock_host.name], result_action="return_value"
        )

        assert code == 0
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_sync(self, mock_host):
        """
        Test refreshing a host's repos and updates with full sync
        """
        code = host_module.app(
            ["refresh", mock_host.name, "--sync"], result_action="return_value"
        )

        assert code == 0
        assert hasattr(mock_host, "repos_synced")
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_discover(self, mock_host):
        """
        Test refreshing a host with discovery option.
        """
        code = host_module.app(
            ["refresh", mock_host.name, "--discover"], result_action="return_value"
        )

        assert code == 0
        assert hasattr(mock_host, "discovered")
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_discover_and_sync(self, mock_host):
        """
        Test refreshing a host with both discover and sync options.
        """
        code = host_module.app(
            ["refresh", mock_host.name, "--discover", "--sync"],
            result_action="return_value",
        )

        assert code == 0
        assert hasattr(mock_host, "discovered")
        assert hasattr(mock_host, "repos_synced")
        assert hasattr(mock_host, "updates_refreshed")

    def test_discover_exception(self, mock_host, capsys):
        """
        Test refreshing a host when discover operation fails.
        """
        mock_host.discover.side_effect = Exception("Discovery failed")

        code = host_module.app(
            ["refresh", mock_host.name, "--discover"], result_action="return_value"
        )

        assert code == 2  # Application error
        assert "Discovery failed" in capsys.readouterr().out

    def test_sync_repos_exception(self, mock_host, capsys):
        """
        Test refreshing a host when sync_repos operation fails.
        """
        mock_host.sync_repos.side_effect = Exception("Repository sync failed")

        code = host_module.app(
            ["refresh", mock_host.name, "--sync"], result_action="return_value"
        )

        assert code == 2  # Application error
        assert "Repository sync failed" in capsys.readouterr().out

    def test_refresh_updates_exception(self, mock_host, capsys):
        """
        Test refreshing a host when refresh_updates operation fails.
        """
        mock_host.refresh_updates.side_effect = Exception("Update refresh failed")

        code = host_module.app(
            ["refresh", mock_host.name], result_action="return_value"
        )

        assert code == 2  # Application error
        assert "Update refresh failed" in capsys.readouterr().out

    def test_host_not_found(self, mock_host):
        """
        Test refreshing a host that does not exist in the inventory.
        """
        with pytest.raises(SystemExit) as exc_info:
            host_module.app(["refresh", "not_test_host"])

        assert exc_info.value.code == 1  # Input error from converter


class TestPingCommand:
    """Tests for the 'host ping' command."""

    @pytest.mark.parametrize(
        "online",
        [True, False],
        ids=["online", "offline"],
    )
    def test_ping_existing_host(self, mock_host, online):
        """
        Test pinging an existing host (online or offline both succeed).

        Ping does not signal reachability via exit code; it always succeeds
        for a resolvable host.
        """
        mock_host.online = online

        code = host_module.app(["ping", mock_host.name], result_action="return_value")

        assert code is None  # ping returns None (success)

    def test_ping_host_not_found(self, mock_host):
        """
        Test pinging a host that does not exist in the inventory.
        """
        with pytest.raises(SystemExit) as exc_info:
            host_module.app(["ping", "not_exists_yo"])

        assert exc_info.value.code == 1  # Input error from converter


class TestHostCommands:
    """Tests for general host command functionality."""

    @pytest.mark.parametrize(
        "command,args",
        [
            ("show", ["testhost"]),
            ("discover", ["testhost"]),
            ("refresh", ["testhost"]),
            ("ping", ["testhost"]),
        ],
        ids=["show", "discover", "refresh", "ping"],
    )
    def test_commands_bail_with_uninitialized_inventory(
        self, mocker, command, args, capsys
    ):
        """Test that all commands bail out with an uninitialized inventory."""
        # Patch the inventory to simulate it being uninitialized
        mocker.patch("exosphere.context.inventory", None)

        with pytest.raises(SystemExit) as exc_info:
            host_module.app([command] + args)

        assert exc_info.value.code == 1  # Input error from converter
        assert "Inventory is not initialized" in capsys.readouterr().err
