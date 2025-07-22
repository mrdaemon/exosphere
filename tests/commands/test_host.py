import pytest
from typer.testing import CliRunner

from exosphere.commands import host as host_module
from exosphere.commands import utils as utils_module
from exosphere.data import Update

runner = CliRunner()


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


def test_show_host_basic(mock_host, patch_context_inventory):
    """
    Test showing a host with basic information.
    """
    result = runner.invoke(host_module.app, ["show", mock_host.name])
    assert result.exit_code == 0


def test_show_host_with_updates(mock_host, patch_context_inventory):
    """
    Test showing a host with updates information.
    """
    result = runner.invoke(host_module.app, ["show", mock_host.name, "--updates"])
    assert result.exit_code == 0


def test_show_host_with_security_only(mock_host, patch_context_inventory):
    """
    Test showing a host with security updates only.
    """
    result = runner.invoke(
        host_module.app, ["show", mock_host.name, "--updates", "--security-only"]
    )
    assert result.exit_code == 0


def test_show_host_not_found(mock_host, patch_context_inventory):
    """
    Test showing a host that does not exist in the inventory.
    """

    result = runner.invoke(host_module.app, ["show", "not_test_host"])

    assert result.exit_code == 1
    assert not hasattr(mock_host, "discovered")


def test_show_host_with_last_refresh_date(mock_host, patch_context_inventory):
    """
    Test showing a host with a last refresh date displayed.
    """
    from datetime import datetime

    # Set a last refresh date on the mock host
    mock_host.last_refresh = datetime(2025, 7, 22, 14, 30, 45)

    result = runner.invoke(host_module.app, ["show", mock_host.name])

    assert result.exit_code == 0
    assert "Tue Jul 22 14:30:45 2025" in result.output


def test_show_host_security_only_with_no_updates(mock_host, patch_context_inventory):
    """
    Test showing security-only updates when --no-updates is specified.
    """
    result = runner.invoke(
        host_module.app, ["show", mock_host.name, "--no-updates", "--security-only"]
    )

    assert result.exit_code == 1
    assert (
        "Warning: --security-only option is only valid with --updates" in result.output
    )


def test_show_host_no_updates_available(mock_host, patch_context_inventory):
    """
    Test host show with no updates available.
    """
    # Clear all updates from the mock host
    mock_host.updates = []
    mock_host.security_updates = []

    result = runner.invoke(host_module.app, ["show", mock_host.name, "--updates"])

    assert result.exit_code == 0
    assert "No updates available for this host." in result.output


def test_discover_host(mock_host, patch_context_inventory):
    """
    Test discovering a host that exists in the inventory.
    """
    result = runner.invoke(host_module.app, ["discover", mock_host.name])

    assert result.exit_code == 0
    assert hasattr(mock_host, "discovered")


def test_discover_host_not_found(mock_host, patch_context_inventory):
    """
    Test discovering a host that does not exist in the inventory.
    """

    result = runner.invoke(host_module.app, ["discover", "not_test_host"])

    assert result.exit_code == 1
    assert not hasattr(mock_host, "discovered")


def test_discover_host_with_exception(mock_host, patch_context_inventory):
    """
    Test discovering a host when host.discover() raises an exception.
    """
    # Make discover() raise an exception
    mock_host.discover.side_effect = Exception("Connection failed")

    result = runner.invoke(host_module.app, ["discover", mock_host.name])

    assert result.exit_code == 1
    assert "Connection failed" in result.output


def test_refresh_host(mock_host, patch_context_inventory):
    """
    Test refreshing a host's updates without full sync
    """
    result = runner.invoke(host_module.app, ["refresh", mock_host.name])

    assert result.exit_code == 0
    assert hasattr(mock_host, "updates_refreshed")


def test_refresh_host_sync(mock_host, patch_context_inventory):
    """
    Test refreshing a host's repos and updates with full sync
    """
    result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--sync"])

    assert result.exit_code == 0
    assert hasattr(mock_host, "repos_synced")
    assert hasattr(mock_host, "updates_refreshed")


def test_refresh_host_with_discover(mock_host, patch_context_inventory):
    """
    Test refreshing a host with discovery option.
    """
    result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--discover"])

    assert result.exit_code == 0
    assert hasattr(mock_host, "discovered")
    assert hasattr(mock_host, "updates_refreshed")


def test_refresh_host_with_discover_and_sync(mock_host, patch_context_inventory):
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


def test_refresh_host_discover_exception(mock_host, patch_context_inventory):
    """
    Test refreshing a host when discover operation fails.
    """
    mock_host.discover.side_effect = Exception("Discovery failed")

    result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--discover"])

    assert result.exit_code == 1
    assert "Discovery failed" in result.output


def test_refresh_host_sync_repos_exception(mock_host, patch_context_inventory):
    """
    Test refreshing a host when sync_repos operation fails.
    """
    mock_host.sync_repos.side_effect = Exception("Repository sync failed")

    result = runner.invoke(host_module.app, ["refresh", mock_host.name, "--sync"])

    assert result.exit_code == 1
    assert "Repository sync failed" in result.output


def test_refresh_host_refresh_updates_exception(mock_host, patch_context_inventory):
    """
    Test refreshing a host when refresh_updates operation fails.
    """
    mock_host.refresh_updates.side_effect = Exception("Update refresh failed")

    result = runner.invoke(host_module.app, ["refresh", mock_host.name])

    assert result.exit_code == 1
    assert "Update refresh failed" in result.output


def test_refresh_host_not_found(mock_host, patch_context_inventory):
    result = runner.invoke(host_module.app, ["refresh", "not_test_host"])

    assert result.exit_code == 1


@pytest.mark.parametrize(
    "host_exists,online,expected_exit_code",
    [
        (True, True, 0),
        (True, False, 0),
        (False, None, 1),
    ],
    ids=["exists_online", "exists_offline", "not_exists"],
)
def test_ping_host_parametrized(
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


def test_commands_bail_with_uninitialized_inventory(mocker):
    """
    Test that commands bail out with an uninitialized inventory.
    """

    # Patch the inventory to simulate it being uninitialized
    mocker.patch("exosphere.context.inventory", None)

    result = runner.invoke(host_module.app, ["show", "testhost"])

    assert result.exit_code == 1
    assert "Inventory is not initialized" in result.output
