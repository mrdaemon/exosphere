import pytest
from typer.testing import CliRunner

from exosphere.commands import sudo
from exosphere.config import Configuration
from exosphere.objects import Host
from exosphere.security import SudoPolicy

runner = CliRunner()


@pytest.fixture(autouse=True)
def app_config(mocker):
    """
    Patch app_config with a fresh configuration object.
    """
    config = Configuration()

    mocker.patch("exosphere.commands.sudo.app_config", config)
    return config


@pytest.fixture(autouse=True)
def mock_inventory(mocker):
    """
    Patch the inventory to return a dummy host.
    """
    mock_inventory = mocker.MagicMock()
    mock_inventory.get_host.return_value = None
    mocker.patch("exosphere.commands.sudo.context.inventory", mock_inventory)
    return mock_inventory


@pytest.fixture
def dummy_host(mocker):
    """
    Fixture to create a dummy host object for testing.
    """

    dummy_host = mocker.MagicMock(spec=Host)
    dummy_host.name = "dummy_host"
    dummy_host.ip = "192.168.1.1"
    dummy_host.package_manager = "apt"
    dummy_host.sudo_policy = SudoPolicy.SKIP  # Match the default sudo policy
    dummy_host.username = None

    return dummy_host


def test_sudo_policy():
    """
    Test that the sudo policy command returns the global sudo policy
    from the configuration.
    """

    expected_policy = Configuration.DEFAULTS["options"]["default_sudo_policy"]

    result = runner.invoke(sudo.app, ["policy"])
    assert result.exit_code == 0
    assert f"Global SudoPolicy: {expected_policy}" in result.output


def test_check_with_invalid_host(mocker):
    """
    Test that help is displayed when no host is specified.
    """

    result = runner.invoke(sudo.app, ["check", "testhost"])
    assert result.exit_code != 0
    assert "Host 'testhost' not found in inventory!" in result.output


def test_check(mocker, mock_inventory, dummy_host):
    """
    Test the sudo check command with a dummy host.
    """

    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["check", "dummy_host"])

    assert result.exit_code == 0
    assert "Sudo Policy for dummy_host" in result.output
    assert "Host Policy:" in result.output
    assert "skip (global)" in result.output
    assert "Can Synchronize Catalog:  No" in result.output
    assert "operations require sudo privileges" in result.output


def test_check_with_local_policy(mocker, mock_inventory, dummy_host):
    """
    Test the sudo check command with a local policy set on the host.
    """

    dummy_host.sudo_policy = SudoPolicy.NOPASSWD
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["check", "dummy_host"])

    assert result.exit_code == 0
    assert "nopasswd (local)" in result.output
    assert "Can Synchronize Catalog:  Yes" in result.output
    assert "operations require sudo privileges" not in result.output


def test_check_with_unknown_package_manager(mocker, mock_inventory, dummy_host):
    """
    Test the sudo check command with a host that has an unknown package manager.
    """

    dummy_host.package_manager = "TOTALLY_UNKNOWN_PROVIDER"
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["check", "dummy_host"])

    assert result.exit_code != 0
    assert (
        "Host 'dummy_host' has an unknown package manager: TOTALLY_UNKNOWN_PROVIDER"
        in result.output
    )


def test_check_with_no_package_manager(mocker, mock_inventory, dummy_host):
    """
    Test the sudo check command with a host that has no package manager.
    """

    dummy_host.package_manager = None
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["check", "dummy_host"])

    assert result.exit_code != 0
    assert "Host 'dummy_host' does not have a package manager defined" in result.output


def test_providers(mocker):
    """
    Test that the sudo providers command lists all available sudo providers.
    """

    result = runner.invoke(sudo.app, ["providers"])

    assert result.exit_code == 0
    assert "Providers Requirements" in result.output
    assert "Apt" in result.output
    assert "Dnf" in result.output
    assert "Debian/Ubuntu Derivatives" in result.output
    assert "Requires Sudo" in result.output
    assert "No Privileges" in result.output


def test_providers_with_unknown_provider(mocker):
    result = runner.invoke(sudo.app, ["providers", "unknown_provider"])

    assert result.exit_code != 0
    assert "No such provider: unknown_provider" in result.output
