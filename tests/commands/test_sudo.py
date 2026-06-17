from unittest.mock import MagicMock

import pytest

from exosphere.commands import sudo
from exosphere.commands import utils as utils_module
from exosphere.config import Configuration
from exosphere.objects import Host
from exosphere.security import SudoPolicy


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the sudo command module."""
    patch_console(sudo)


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
    mocker.patch.object(utils_module.context, "inventory", mock_inventory)
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
    dummy_host.supported = True

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


class TestPolicyCommand:
    """Tests for the 'sudo policy' command."""

    def test_shows_global_policy(self, capsys):
        """
        Test that the sudo policy command returns the global sudo policy
        from the configuration.
        """
        expected_policy = Configuration.DEFAULTS["options"]["default_sudo_policy"]

        code = sudo.app(["policy"], result_action="return_value")
        assert code is None  # FIXME: policy returns None?
        assert f"Global SudoPolicy: {expected_policy}" in capsys.readouterr().out


class TestCheckCommand:
    """Tests for the 'sudo check' command."""

    def test_with_invalid_host(self, capsys):
        """
        Test that an unknown host is rejected by the converter.

        Host resolution happens in a converter, so an unknown name is an
        input error (exit 1) raised during argument binding.
        """
        with pytest.raises(SystemExit) as exc_info:
            sudo.app(["check", "testhost"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Host 'testhost' not found in inventory" in captured.out + captured.err

    def test_basic_check(self, mock_inventory, dummy_host, capsys):
        """
        Test the sudo check command with a dummy host.
        """
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(["check", "dummy_host"], result_action="return_value")

        captured = capsys.readouterr()
        assert code == 0
        assert "Sudo Policy for dummy_host" in captured.out
        assert "Host Policy:" in captured.out
        assert "skip (global)" in captured.out
        assert "Can Sync Repositories:  No" in captured.out
        assert "Can Refresh Updates:    Yes" in captured.out
        assert "operations require sudo privileges" in captured.err

    def test_with_local_policy(self, mock_inventory, dummy_host, capsys):
        """
        Test the sudo check command with a local policy set on the host.
        """
        dummy_host.sudo_policy = SudoPolicy.NOPASSWD
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(["check", "dummy_host"], result_action="return_value")

        captured = capsys.readouterr()
        assert code == 0
        assert "nopasswd (local)" in captured.out
        assert "Can Sync Repositories:  Yes" in captured.out
        assert "Can Refresh Updates:    Yes" in captured.out
        assert "operations require sudo privileges" not in captured.err

    def test_with_unknown_package_manager(self, mock_inventory, dummy_host, capsys):
        """
        Test the sudo check command with a host that has an unknown package manager.
        """
        dummy_host.package_manager = "TOTALLY_UNKNOWN_PROVIDER"
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(["check", "dummy_host"], result_action="return_value")

        assert code == 2  # Application error
        assert (
            "Host 'dummy_host' has an unknown package manager: TOTALLY_UNKNOWN_PROVIDER"
            in capsys.readouterr().err
        )

    def test_with_no_package_manager(self, mock_inventory, dummy_host, capsys):
        """
        Test the sudo check command with a host that has no package manager.
        """
        dummy_host.package_manager = None
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(["check", "dummy_host"], result_action="return_value")

        assert code == 2  # Application error
        assert "has not been discovered yet" in capsys.readouterr().err

    def test_with_unsupported_host(self, mock_inventory, dummy_host, capsys):
        """
        Test the sudo check command with a host that is unsupported.
        """
        dummy_host.supported = False
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(["check", "dummy_host"], result_action="return_value")

        assert code == 1  # Input error
        assert (
            "Host 'dummy_host' is not running a supported OS."
            in capsys.readouterr().err
        )


class TestProvidersCommand:
    """Tests for the 'sudo providers' command."""

    def test_lists_all_providers(self, mock_pkgmanager_factory, capsys):
        """
        Test that the sudo providers command lists all available sudo providers.
        """
        code = sudo.app(["providers"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "Providers Requirements" in out
        assert "Apt" in out
        assert "Dnf" in out
        assert "Yum" in out
        assert "Pkg" in out
        assert "TestGuy" in out

        assert "Debian/Ubuntu Derivatives" in out
        assert "Fedora/RHEL/CentOS" in out
        assert "FreeBSD" in out
        assert "RHEL/CentOS 7 and earlier" in out
        assert "testguy" in out  # Match for no Description in map

        assert out.count("Requires Sudo") == 3
        assert out.count("No Privileges") == 7

    def test_with_unknown_provider(self, mock_pkgmanager_factory, capsys):
        """
        Ensure the program returns an error on invalid providers
        """
        code = sudo.app(["providers", "unknown_provider"], result_action="return_value")

        assert code == 1  # Input error
        assert "No such provider: unknown_provider" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "missing_method",
        ["reposync", "get_updates"],
        ids=["missing_reposync", "missing_get_updates"],
    )
    def test_with_non_conforming_provider(
        self, mocker, mock_pkgmanager_factory, missing_method, capsys
    ):
        """
        Ensure the program returns non-zero and an error when the
        provider class does not have the 'reposync' or 'get_updates' methods.
        """
        bad_provider = mocker.MagicMock(name="BadProvider")
        bad_provider.__qualname__ = "BadProvider"
        bad_provider.SUDOERS_COMMANDS = []

        # Create both methods initially
        bad_provider.reposync = mocker.MagicMock(name="reposync")
        bad_provider.get_updates = mocker.MagicMock(name="get_updates")

        # Delete the specific method we want to test
        delattr(bad_provider, missing_method)

        # Add the bad provider to the registry
        registry = mock_pkgmanager_factory.get_registry.return_value
        registry["badprovider"] = bad_provider

        code = sudo.app(["providers"], result_action="return_value")

        captured = capsys.readouterr()
        assert code == 0  # Command should still succeed but show warning
        assert (
            "Provider badprovider does not implement required methods!" in captured.err
        )
        assert "This is likely a bug." in captured.err


class TestGenerateCommand:
    """Tests for the 'sudo generate' command."""

    def test_no_arguments(self, capsys):
        """
        Test that we handle no arguments gracefully
        """
        code = sudo.app(["generate"], result_action="return_value")

        assert code == 1  # Input error
        assert "You must specify either --host or --provider" in capsys.readouterr().err

    def test_host_and_provider_mutually_exclusive(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with both host and provider specified.
        This should return a failure since they are mutually exclusive.
        """
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        with pytest.raises(SystemExit) as exc_info:
            sudo.app(["generate", "--host", "dummy_host", "--provider", "apt"])

        assert exc_info.value.code == 1
        assert "Mutually exclusive arguments" in capsys.readouterr().err

    def test_with_host(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a standard host with username
        """
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Generated for Debian" in out
        assert "Cmnd_Alias EXOSPHERE_CMDS = /bin/test-command" in out
        assert "testuser ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_invalid_host(self, mock_inventory, mock_pkgmanager_factory, capsys):
        """
        Test the sudo generate command with an invalid host.
        """
        mock_inventory.get_host.return_value = None

        with pytest.raises(SystemExit) as exc_info:
            sudo.app(["generate", "--host", "invalid_host"])

        assert exc_info.value.code == 1  # Input error from converter
        captured = capsys.readouterr()
        assert (
            "Host 'invalid_host' not found in inventory" in captured.out + captured.err
        )

    def test_with_host_undiscovered(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a host that is not discovered.
        """
        dummy_host.package_manager = None  # Simulate an undiscovered host
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host"], result_action="return_value"
        )

        assert code == 2  # Application error
        assert "has not been discovered yet" in capsys.readouterr().err

    def test_with_host_unsupported(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a host that is unsupported.
        """
        dummy_host.supported = False
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host"], result_action="return_value"
        )

        assert code == 1  # Input error
        assert (
            "Host 'dummy_host' is not running a supported OS."
            in capsys.readouterr().err
        )

    def test_with_host_no_username_fallback(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a standard host without username
        Ensure it falls back to the current user.
        """
        dummy_host.username = None
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Generated for Debian" in out
        assert "current_user ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_host_global_username_fallback(
        self, app_config, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a standard host without username
        but with global username set
        """
        app_config["options"]["default_username"] = "global_user"
        dummy_host.username = None

        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host"], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Generated for Debian" in out
        assert "current_user" not in out
        assert "global_user ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_host_username_precedence(
        self, app_config, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a host and a specified username.
        Ensure the precedence works as expected.
        """
        app_config["options"]["default_username"] = "global_user"
        dummy_host.username = "host_user"
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        code = sudo.app(
            ["generate", "--host", "dummy_host", "--user", "specified_user"],
            result_action="return_value",
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Generated for Debian" in out
        assert "global_user" not in out
        assert "host_user" not in out
        assert "specified_user ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_host_no_username_fallback_fails(
        self,
        mocker,
        app_config,
        mock_inventory,
        dummy_host,
        mock_pkgmanager_factory,
        capsys,
    ):
        """
        Test the sudo generate command with a host that has no username fallback.
        This scenario should not really happen but should be handled gracefully.
        """
        mocker.patch("fabric.util.get_local_user", return_value=None)
        app_config["options"]["default_username"] = None
        dummy_host.username = None
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        with pytest.raises(SystemExit) as exc_info:
            sudo.app(["generate", "--host", "dummy_host"])

        assert exc_info.value.code == 1  # Input error from _get_username
        assert "No username could be selected" in capsys.readouterr().err

    def test_with_username_provided_but_invalid(
        self, mock_inventory, dummy_host, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with an invalid username.
        This should raise an error.
        """
        mock_inventory.get_host.return_value = dummy_host
        mock_inventory.hosts = [dummy_host]

        with pytest.raises(SystemExit) as exc_info:
            sudo.app(["generate", "--host", "dummy_host", "--user", "invalid\\;;user!"])

        assert exc_info.value.code == 1  # Input error from _get_username
        assert "Invalid username 'invalid\\;;user!'" in capsys.readouterr().err

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
    def test_with_provider(
        self,
        mock_pkgmanager_factory,
        provider_name,
        provider_desc,
        expected_commands,
        capsys,
    ):
        """
        Test the sudo generate command with a specific provider.
        """
        code = sudo.app(
            ["generate", "--provider", provider_name], result_action="return_value"
        )

        out = capsys.readouterr().out
        assert code == 0
        assert f"Generated for {provider_desc}" in out
        assert (
            f"Cmnd_Alias EXOSPHERE_CMDS = {', '.join(expected_commands) if len(expected_commands) > 1 else expected_commands[0]}"
            in out
        )
        assert "ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_unknown_provider(self, capsys):
        """
        Ensure that we handle unknown providers gracefully.
        """
        code = sudo.app(
            ["generate", "--provider", "unknown_provider"],
            result_action="return_value",
        )

        assert code == 1  # Input error
        assert "No such provider: unknown_provider" in capsys.readouterr().err

    def test_with_provider_and_username(
        self, app_config, mock_pkgmanager_factory, capsys
    ):
        """
        Test the sudo generate command with a specific provider and a specified username.
        """
        app_config["options"]["default_username"] = "global_user"

        code = sudo.app(
            ["generate", "--provider", "apt", "--user", "specified_user"],
            result_action="return_value",
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "Generated for Debian" in out
        assert "global_user" not in out
        assert "specified_user ALL=(root) NOPASSWD: EXOSPHERE_CMDS" in out

    def test_with_provider_no_sudo_required(self, mock_pkgmanager_factory, capsys):
        """
        Test the sudo generate command with a specific provider but
        it does not require sudo
        """
        code = sudo.app(["generate", "--provider", "dnf"], result_action="return_value")

        assert code == 3  # Nothing to do
        assert (
            "Provider 'dnf' does not require any sudo commands"
            in capsys.readouterr().err
        )

    def test_with_provider_no_sudo_commands_defined(
        self, mock_pkgmanager_factory, capsys
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

        code = sudo.app(
            ["generate", "--provider", "fucky"], result_action="return_value"
        )

        captured = capsys.readouterr()
        assert code == 2  # Application error
        assert "ALL=(root) NOPASSWD: EXOSPHERE_CMDS" not in captured.out
        assert "Provider 'fucky' does not define any sudo commands!" in captured.err


class TestSudoCommands:
    """Common Tests across sudo commands"""

    @pytest.mark.parametrize(
        "command,args",
        [
            ("check", ["testhost"]),
            ("generate", ["--host", "testhost"]),
        ],
        ids=["check", "generate"],
    )
    def test_commands_bail_with_uninitialized_inventory(
        self, mocker, command, args, capsys
    ):
        """Test that sudo commands bail out with an uninitialized inventory."""
        # Patch the inventory to simulate it being uninitialized
        mocker.patch.object(utils_module.context, "inventory", None)

        with pytest.raises(SystemExit) as exc_info:
            sudo.app([command] + args)

        assert exc_info.value.code == 1  # Input error from converter
        captured = capsys.readouterr()
        assert "Inventory is not initialized" in captured.out + captured.err
