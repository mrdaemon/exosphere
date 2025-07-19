from unittest.mock import MagicMock

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
    dummy_host.username = "testuser"

    return dummy_host


def make_package_provider(
    classname="Apt",
    sudoers_command=["/bin/test-command"],
    sudo_sync=True,
    sudo_updates=False,
):
    """
    Fixture to mock the package provider for testing.
    """

    mock_provider = MagicMock(name=classname, isinstance=False)
    mock_provider.SUDOERS_COMMANDS = sudoers_command
    mock_provider.__qualname__ = classname

    reposync_method = MagicMock(name="reposync")
    get_updates_method = MagicMock(name="get_updates")

    if sudo_sync:
        reposync_method.__requires_sudo = True
    else:
        delattr(reposync_method, "__requires_sudo")

    if sudo_updates:
        get_updates_method.__requires_sudo = True
    else:
        delattr(get_updates_method, "__requires_sudo")

    mock_provider.reposync = reposync_method
    mock_provider.get_updates = get_updates_method

    return mock_provider


@pytest.fixture
def mock_pkgmanager_factory(mocker):
    """
    Fixture to mock the package manager factory.
    Includes normal providers and some funky test fixtures
    """

    registry = {
        "apt": make_package_provider(),  # Default apt
        "dnf": make_package_provider(
            classname="Dnf",
            sudoers_command=[],
            sudo_sync=False,
            sudo_updates=False,
        ),
        "yum": make_package_provider(
            classname="Yum",
            sudoers_command=[],
            sudo_sync=False,
            sudo_updates=False,
        ),
        "pkg": make_package_provider(
            classname="Pkg",
            sudoers_command=[],
            sudo_sync=False,
            sudo_updates=False,
        ),
        "testguy": make_package_provider(
            classname="TestGuy",
            sudoers_command=["/sbin/testguy-sync", "/usr/sbin/testguy-update"],
            sudo_sync=True,
            sudo_updates=True,
        ),
    }

    mock_factory_class = mocker.patch("exosphere.commands.sudo.PkgManagerFactory")
    mock_factory_class.get_registry.return_value = registry
    return mock_factory_class


@pytest.fixture(autouse=True)
def patch_local_user(mocker):
    """
    Patch fabric.util.get_local_user to return a fixed username.
    """
    mocker.patch("fabric.util.get_local_user", return_value="current_user")


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
    assert result.exit_code == 1
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

    assert result.exit_code == 1
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

    assert result.exit_code == 1
    assert "Host 'dummy_host' does not have a package manager defined" in result.output


def test_providers(mocker, mock_pkgmanager_factory):
    """
    Test that the sudo providers command lists all available sudo providers.
    """

    result = runner.invoke(sudo.app, ["providers"])

    assert result.exit_code == 0
    assert "Providers Requirements" in result.output
    assert "Apt" in result.output
    assert "Dnf" in result.output
    assert "Yum" in result.output
    assert "Pkg" in result.output
    assert "TestGuy" in result.output

    assert "Debian/Ubuntu Derivatives" in result.output
    assert "Fedora/RHEL/CentOS" in result.output
    assert "FreeBSD" in result.output
    assert "RHEL/CentOS 7 and earlier" in result.output
    assert "testguy" in result.output  # Match for no Description in map

    assert result.output.count("Requires Sudo") == 3
    assert result.output.count("No Privileges") == 7


def test_providers_with_unknown_provider(mocker):
    """
    Ensure the program returns an error on invalid providers
    """
    result = runner.invoke(sudo.app, ["providers", "unknown_provider"])

    assert result.exit_code == 1
    assert "No such provider: unknown_provider" in result.output


def test_generate_no_arguments(mocker, mock_pkgmanager_factory):
    """
    Test that we handle no arguments gracefully
    """
    result = runner.invoke(sudo.app, ["generate"])

    assert result.exit_code == 1
    assert "You must specify either --host or --provider" in result.output


def test_generate_host_and_provider(
    mocker, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with both host and provider specified.
    This should raise an error since only one can be specified at a time.
    """
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(
        sudo.app, ["generate", "--host", "dummy_host", "--provider", "apt"]
    )

    assert result.exit_code == 1
    assert "--host and --provider are mutually exclusive" in result.output


def test_generate_with_host(
    mocker, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a standard host with username
    """
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["generate", "--host", "dummy_host"])

    assert result.exit_code == 0
    assert "Generated for Debian" in result.output
    assert "Cmnd_Alias EXOSPHERE_CMDS = /bin/test-command" in result.output
    assert "testuser ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_invalid_host(
    mocker, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with an invalid host.
    """
    mock_inventory.get_host.return_value = None

    result = runner.invoke(sudo.app, ["generate", "--host", "invalid_host"])

    assert result.exit_code == 1
    assert "Host 'invalid_host' not found in inventory!" in result.output


def test_generate_with_host_but_its_undiscovered(
    mocker, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a host that is not discovered.
    """
    dummy_host.package_manager = None  # Simulate an undiscovered host
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["generate", "--host", "dummy_host"])

    assert result.exit_code == 1
    assert "Host 'dummy_host' does not have a package manager" in result.output


def test_generate_with_host_no_username(
    mocker, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a standard host without username
    Ensure it falls back to the current user.
    """
    dummy_host.username = None
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["generate", "--host", "dummy_host"])

    assert result.exit_code == 0
    assert "Generated for Debian" in result.output
    assert "current_user ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_host_no_username_global_username(
    mocker, app_config, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a standard host without username
    but with global username set
    """
    app_config["options"]["default_username"] = "global_user"
    dummy_host.username = None

    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["generate", "--host", "dummy_host"])

    assert result.exit_code == 0
    assert "Generated for Debian" in result.output
    assert "current_user" not in result.output
    assert "global_user ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_host_specified_username(
    mocker, app_config, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a host and a specified username.
    Ensure the precedence works as expected.
    """
    app_config["options"]["default_username"] = "global_user"
    dummy_host.username = "host_user"
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(
        sudo.app, ["generate", "--host", "dummy_host", "--user", "specified_user"]
    )

    assert result.exit_code == 0
    assert "Generated for Debian" in result.output
    assert "global_user" not in result.output
    assert "host_user" not in result.output
    assert "specified_user ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_host_but_no_password_fallback_somehow(
    mocker, app_config, mock_inventory, dummy_host, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a host that has no password fallback.
    This scenario should not really happen but should be handled gracefully.
    """
    mocker.patch("fabric.util.get_local_user", return_value=None)
    app_config["options"]["default_username"] = None
    dummy_host.username = None
    mock_inventory.get_host.return_value = dummy_host
    mock_inventory.hosts = [dummy_host]

    result = runner.invoke(sudo.app, ["generate", "--host", "dummy_host"])

    assert result.exit_code == 1
    assert "No username could be selected" in result.output


@pytest.mark.parametrize(
    "provider_name, provider_desc, expected_commands",
    [
        ("apt", "Debian/Ubuntu Derivatives", ["/bin/test-command"]),
        ("testguy", "testguy", ["/sbin/testguy-sync", "/usr/sbin/testguy-update"]),
    ],
    ids=[
        "single_command",
        "multiple_commands",
    ],
)
def test_generate_with_provider(
    mocker, mock_pkgmanager_factory, provider_name, provider_desc, expected_commands
):
    """
    Test the sudo generate command with a specific provider.
    """
    result = runner.invoke(sudo.app, ["generate", "--provider", provider_name])

    assert result.exit_code == 0
    assert f"Generated for {provider_desc}" in result.output
    assert (
        f"Cmnd_Alias EXOSPHERE_CMDS = {', '.join(expected_commands) if len(expected_commands) > 1 else expected_commands[0]}"
        in result.output
    )
    assert "ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_unknown_provider(mocker):
    """
    Ensure that we handle unknown providers gracefully.
    """
    result = runner.invoke(sudo.app, ["generate", "--provider", "unknown_provider"])

    assert result.exit_code == 1
    assert "No such provider: unknown_provider" in result.output


def test_generate_with_provider_and_username(
    mocker, app_config, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a specific provider and a specified username.
    """
    app_config["options"]["default_username"] = "global_user"

    result = runner.invoke(
        sudo.app, ["generate", "--provider", "apt", "--user", "specified_user"]
    )

    assert result.exit_code == 0
    assert "Generated for Debian" in result.output
    assert "global_user" not in result.output
    assert "specified_user ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" in result.output


def test_generate_with_provider_but_not_sudo(
    mocker, app_config, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a specific provider but
    it does not require sudo
    """
    result = runner.invoke(sudo.app, ["generate", "--provider", "dnf"])

    assert result.exit_code == 0
    assert "Provider 'dnf' does not require any sudo commands" in result.output


def test_generate_with_provider_but_no_sudo_commands(
    mocker, app_config, mock_pkgmanager_factory
):
    """
    Test the sudo generate command with a specific provider but
    it does not have any sudo commands defined.
    This is a bug in the provider implementation.
    """

    # Mock a buggy provider that requires sudo but does not actually
    # define any sudo commands. This should never result in configuration.
    FuckyProvider = make_package_provider(
        classname="FuckyProvider",
        sudoers_command=[],
        sudo_sync=False,
        sudo_updates=True,
    )

    mock_pkgmanager_factory.get_registry.return_value["fucky"] = FuckyProvider

    app_config["options"]["default_username"] = "global_user"

    result = runner.invoke(sudo.app, ["generate", "--provider", "fucky"])

    assert result.exit_code == 1
    assert "ALL=(ALL) NOPASSWD: EXOSPHERE_CMDS" not in result.output
    assert "Provider 'fucky' does not define any sudo commands!" in result.output
