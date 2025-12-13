import pytest
from typer.testing import CliRunner

from exosphere.commands import host as host_module
from exosphere.commands import utils as utils_module
from exosphere.data import Update

runner = CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture(autouse=True)
def patch_console(mocker):
    """
    Patch the Rich console to avoid actual printing during tests.
    """
    mocker.patch.object(utils_module, "console")
    mocker.patch.object(utils_module, "err_console")


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

    def ping():
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
    Patch out the save_inventory function to, well not.
    """
    mocker.patch.object(host_module, "save_inventory")


class TestShowCommand:
    """Tests for the 'host show' command."""

    def test_basic_info(self, mock_host, patch_context_inventory):
        """
        Test showing a host with basic information.
        """
        result = runner.invoke(host_module.app, ["show", mock_host.name])
        assert result.exit_code == 0

    def test_with_updates(self, mock_host, patch_context_inventory):
        """
        Test showing a host with updates information.
        """
        result = runner.invoke(host_module.app, ["show", mock_host.name, "--updates"])
        assert result.exit_code == 0

    def test_with_security_only(self, mock_host, patch_context_inventory):
        """
        Test showing a host with security updates only.
        """
        result = runner.invoke(
            host_module.app, ["show", mock_host.name, "--updates", "--security-only"]
        )
        assert result.exit_code == 0

    def test_host_not_found(self, mock_host, patch_context_inventory):
        """
        Test showing a host that does not exist in the inventory.
        """
        result = runner.invoke(host_module.app, ["show", "not_test_host"])

        assert result.exit_code == 2
        assert not hasattr(mock_host, "discovered")

    def test_with_last_refresh_date(self, mock_host, patch_context_inventory):
        """
        Test showing a host with a last refresh date displayed.
        """
        from datetime import datetime, timezone

        # Set a UTC datetime on the mock host
        utc_time = datetime(2025, 7, 22, 14, 30, 45, tzinfo=timezone.utc)
        mock_host.last_refresh = utc_time

        result = runner.invoke(host_module.app, ["show", mock_host.name])

        assert result.exit_code == 0

        # Output should display local time
        expected_local = utc_time.astimezone().strftime("%a %b %d %H:%M:%S %Y")
        assert expected_local in result.output

    def test_security_only_without_updates_flag(
        self, mock_host, patch_context_inventory
    ):
        """
        Test showing security-only updates when --no-updates is specified.
        """
        result = runner.invoke(
            host_module.app, ["show", mock_host.name, "--no-updates", "--security-only"]
        )

        assert result.exit_code == 2  # Argument error
        assert (
            "Error: --security-only option is only valid with --updates"
            in result.output
        )

    def test_no_updates_available(self, mock_host, patch_context_inventory):
        """
        Test host show with no updates available.
        """
        # Clear all updates from the mock host
        mock_host.updates = []
        mock_host.security_updates = []

        result = runner.invoke(host_module.app, ["show", mock_host.name, "--updates"])

        assert result.exit_code == 0
        assert "No updates available for this host." in result.output

    def test_unsupported_host_display(self, mock_host, patch_context_inventory):
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

        result = runner.invoke(host_module.app, ["show", mock_host.name])

        assert result.exit_code == 0
        assert "irix (Unsupported OS)" in result.output

    def test_unsupported_host_no_updates_display(
        self, mock_host, patch_context_inventory
    ):
        """
        Test that updates are not shown for unsupported hosts.
        """
        # Mark host as unsupported
        mock_host.supported = False
        mock_host.online = True
        mock_host.os = "Darwin"

        result = runner.invoke(host_module.app, ["show", mock_host.name, "--updates"])

        assert result.exit_code == 0
        assert "Update info is not available for unsupported hosts." in result.output


class TestDiscoverCommand:
    """Tests for the 'host discover' command."""

    def test_basic_discovery(self, mock_host, patch_context_inventory):
        """
        Test discovering a host that exists in the inventory.
        """
        result = runner.invoke(host_module.app, ["discover", mock_host.name])

        assert result.exit_code == 0
        assert hasattr(mock_host, "discovered")

    def test_host_not_found(self, mock_host, patch_context_inventory):
        """
        Test discovering a host that does not exist in the inventory.
        """
        result = runner.invoke(host_module.app, ["discover", "not_test_host"])

        assert result.exit_code == 2  # Expect argument error
        assert not hasattr(mock_host, "discovered")

    def test_with_exception(self, mock_host, patch_context_inventory):
        """
        Test discovering a host when host.discover() raises an exception.
        """
        # Make discover() raise an exception
        mock_host.discover.side_effect = Exception("Connection failed")

        result = runner.invoke(host_module.app, ["discover", mock_host.name])

        assert result.exit_code == 1
        assert "Connection failed" in result.output


class TestRefreshCommand:
    """Tests for the 'host refresh' command."""

    def test_basic_refresh(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host's updates without full sync
        """
        result = runner.invoke(host_module.app, ["refresh", mock_host.name])

        assert result.exit_code == 0
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_sync(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host's repos and updates with full sync
        """
        result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--sync"])

        assert result.exit_code == 0
        assert hasattr(mock_host, "repos_synced")
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_discover(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host with discovery option.
        """
        result = runner.invoke(
            host_module.app, ["refresh", mock_host.name, "--discover"]
        )

        assert result.exit_code == 0
        assert hasattr(mock_host, "discovered")
        assert hasattr(mock_host, "updates_refreshed")

    def test_with_discover_and_sync(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host with both discover and sync options.
        """
        result = runner.invoke(
            host_module.app, ["refresh", mock_host.name, "--discover", "--sync"]
        )

        assert result.exit_code == 0
        assert hasattr(mock_host, "discovered")
        assert hasattr(mock_host, "repos_synced")
        assert hasattr(mock_host, "updates_refreshed")

    def test_discover_exception(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host when discover operation fails.
        """
        mock_host.discover.side_effect = Exception("Discovery failed")

        result = runner.invoke(
            host_module.app, ["refresh", mock_host.name, "--discover"]
        )

        assert result.exit_code == 1
        assert "Discovery failed" in result.output

    def test_sync_repos_exception(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host when sync_repos operation fails.
        """
        mock_host.sync_repos.side_effect = Exception("Repository sync failed")

        result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--sync"])

        assert result.exit_code == 1
        assert "Repository sync failed" in result.output

    def test_refresh_updates_exception(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host when refresh_updates operation fails.
        """
        mock_host.refresh_updates.side_effect = Exception("Update refresh failed")

        result = runner.invoke(host_module.app, ["refresh", mock_host.name])

        assert result.exit_code == 1
        assert "Update refresh failed" in result.output

    def test_host_not_found(self, mock_host, patch_context_inventory):
        """
        Test refreshing a host that does not exist in the inventory.
        """
        result = runner.invoke(host_module.app, ["refresh", "not_test_host"])

        assert result.exit_code == 2


class TestPingCommand:
    """Tests for the 'host ping' command."""

    @pytest.mark.parametrize(
        "host_exists,online,expected_exit_code",
        [
            (True, True, 0),
            (True, False, 0),
            (False, None, 2),
        ],
        ids=["exists_online", "exists_offline", "not_exists"],
    )
    def test_ping_scenarios(
        self,
        mocker,
        mock_host,
        fake_inventory,
        host_exists,
        online,
        expected_exit_code,
    ):
        """
        Test pinging a host with different scenarios.
        """
        if host_exists:
            mock_host.online = online
            inventory = fake_inventory
            inventory.hosts = mock_host
        else:
            inventory = fake_inventory
            inventory.hosts = []

        # We patch the context inventory ourselves to use our manipulated mock
        mocker.patch.object(utils_module.context, "inventory", inventory)
        host_name = mock_host.name if host_exists else "not_exists_yo"

        result = runner.invoke(host_module.app, ["ping", host_name])

        assert result.exit_code == expected_exit_code


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
    def test_commands_bail_with_uninitialized_inventory(self, mocker, command, args):
        """
        Test that all commands bail out with an uninitialized inventory.
        """
        # Patch the inventory to simulate it being uninitialized
        mocker.patch("exosphere.context.inventory", None)

        result = runner.invoke(host_module.app, [command] + args)

        assert result.exit_code == 1
        assert "Inventory is not initialized" in result.output


class TestConnectionCleanup:
    """Tests for connection cleanup behavior with ssh_pipelining setting."""

    def _patch_config(self, mocker, ssh_pipelining: bool):
        """Helper to patch app_config with specific ssh_pipelining value."""
        from exosphere.config import Configuration

        config = Configuration()
        config["options"]["cache_autosave"] = False
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch.object(host_module, "app_config", config)

    @pytest.mark.parametrize(
        "pipelining,expect_close,exception",
        [
            (False, True, None),  # closes when pipelining disabled
            (True, False, None),  # keeps when pipelining enabled
            (False, True, Exception("Test error")),  # closes on exception
        ],
        ids=["closes_when_disabled", "keeps_when_enabled", "closes_on_exception"],
    )
    def test_discover_connection_management(
        self,
        mocker,
        mock_host,
        patch_context_inventory,
        pipelining,
        expect_close,
        exception,
    ):
        """
        Test discover command connection management behavior.
        """
        self._patch_config(mocker, pipelining)
        if exception:
            mock_host.discover.side_effect = exception

        result = runner.invoke(host_module.app, ["discover", mock_host.name])

        if exception:
            assert result.exit_code == 1
        else:
            assert result.exit_code == 0

        if expect_close:
            mock_host.close.assert_called_once()
        else:
            mock_host.close.assert_not_called()

    @pytest.mark.parametrize(
        "pipelining,discover,sync,expected_closes",
        [
            (False, False, False, 1),  # basic: refresh_updates only
            (False, True, False, 2),  # with discover
            (False, False, True, 2),  # with sync
            (False, True, True, 3),  # with discover and sync
            (True, True, True, 0),  # pipelining enabled: no closes
        ],
        ids=["basic", "with_discover", "with_sync", "with_both", "pipelining_enabled"],
    )
    def test_refresh_connection_management(
        self,
        mocker,
        mock_host,
        patch_context_inventory,
        pipelining,
        discover,
        sync,
        expected_closes,
    ):
        """
        Test refresh command connection management with various options.
        """
        self._patch_config(mocker, pipelining)

        cmd = ["refresh", mock_host.name]
        if discover:
            cmd.append("--discover")
        if sync:
            cmd.append("--sync")

        result = runner.invoke(host_module.app, cmd)

        assert result.exit_code == 0
        assert mock_host.close.call_count == expected_closes

    @pytest.mark.parametrize(
        "operation,discover,sync",
        [
            ("discover", True, False),  # discover fails
            ("sync_repos", False, True),  # sync fails
            ("refresh_updates", False, False),  # refresh_updates fails
        ],
        ids=["discover_exception", "sync_exception", "refresh_updates_exception"],
    )
    def test_refresh_closes_connection_on_exception(
        self, mocker, mock_host, patch_context_inventory, operation, discover, sync
    ):
        """
        Test that refresh closes connection even when operations fail.
        """
        self._patch_config(mocker, False)
        getattr(mock_host, operation).side_effect = Exception("Test error")

        cmd = ["refresh", mock_host.name]
        if discover:
            cmd.append("--discover")
        if sync:
            cmd.append("--sync")

        result = runner.invoke(host_module.app, cmd)

        assert result.exit_code == 1
        # Should still close connection despite exception
        mock_host.close.assert_called_once()

    @pytest.mark.parametrize(
        "pipelining,expect_close",
        [
            (False, True),  # closes when pipelining disabled
            (True, False),  # keeps when pipelining enabled
        ],
        ids=["closes_when_disabled", "keeps_when_enabled"],
    )
    def test_ping_connection_management(
        self, mocker, mock_host, patch_context_inventory, pipelining, expect_close
    ):
        """
        Test ping command connection management behavior.
        """
        self._patch_config(mocker, pipelining)

        result = runner.invoke(host_module.app, ["ping", mock_host.name])

        assert result.exit_code == 0
        if expect_close:
            mock_host.close.assert_called_once()
        else:
            mock_host.close.assert_not_called()
