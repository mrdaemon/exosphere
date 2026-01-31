from datetime import datetime, timedelta, timezone

import pytest

from exosphere.config import Configuration
from exosphere.data import HostInfo, Update
from exosphere.errors import DataRefreshError, OfflineHostError
from exosphere.objects import Host
from exosphere.providers.api import requires_sudo
from exosphere.security import SudoPolicy


@pytest.fixture
def mock_connection(mocker):
    """
    Fixture to mock the Fabric Connection object.
    Automatically configures context manager support.
    """
    # Mock the Connection class
    mock_connection_class = mocker.patch("exosphere.objects.Connection", autospec=True)

    # Create a mock instance with autospec for better validation
    mock_instance = mock_connection_class.return_value
    mock_instance.__enter__ = mocker.Mock(return_value=mock_instance)
    mock_instance.__exit__ = mocker.Mock(return_value=None)

    # Configure the mocked class to return our context manager-enabled instance
    mock_connection_class.return_value = mock_instance

    return mock_connection_class


@pytest.fixture
def mock_hostinfo(mocker):
    """
    Fixture to mock the HostInfo object.
    A generic host running Debian Linux.
    """
    hostinfo = mocker.Mock(
        spec=HostInfo,
        os="linux",
        version="12",
        flavor="debian",
        package_manager="apt",
        is_supported=True,
    )

    mocker.patch("exosphere.setup.detect.platform_detect", return_value=hostinfo)

    return hostinfo


class TestHostObject:
    @pytest.fixture(autouse=True)
    def mock_config(self, mocker):
        """
        Fixture to mock the application configuration with all its
        default values.
        """

        # Create a fresh configuration object with defaults
        config = Configuration()

        # Patch the app_config to return this configuration
        return mocker.patch("exosphere.objects.app_config", config)

    @pytest.fixture()
    def mock_config_with_sudopolicy_nopasswd(self, mocker, mock_config):
        """
        Fixture to mock the application configuration with all its
        default values, but with a sudo_policy set to NOPASSWD.
        """

        settings = {
            "options": {
                "default_sudo_policy": "nopasswd",
            },
        }

        mock_config.update_from_mapping(settings)

    @pytest.fixture
    def mock_config_with_username(self, mocker, mock_config):
        """
        Fixture to mock the application configuration with all its
        default values, but also includes a set default_username.
        """

        # Set a default username for testing
        settings = {
            "options": {
                "default_username": "test_user",
            },
        }

        mock_config.update_from_mapping(settings)

    def test_host_initialization(self):
        """
        Test the initialization of the Host object.
        """
        host = Host(
            name="test_host",
            ip="172.16.64.10",
            description="Test host",
            port=2222,
            username="test_user",
            connect_timeout=32,
            sudo_policy="skip",
        )

        assert host.name == "test_host"
        assert host.ip == "172.16.64.10"
        assert host.port == 2222
        assert host.connect_timeout == 32
        assert host.username == "test_user"
        assert host.description == "Test host"
        assert host.sudo_policy == SudoPolicy.SKIP

        # Ensure Discovery attributes are initialized to None
        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.updates == []
        assert host.last_refresh is None

        assert host.online is False

    def test_host_initialization_defaults(self):
        """
        Test the initialization of the Host object with default parameters.
        """
        host = Host(
            name="default_host",
            ip="127.0.0.9",
        )

        assert host.name == "default_host"
        assert host.ip == "127.0.0.9"
        assert host.port == 22  # Default port
        assert host.connect_timeout == 10  # Default connect timeout
        assert host.username is None  # Default username is None
        assert host.description is None  # Default description is None
        assert host.sudo_policy == SudoPolicy.SKIP
        assert host.supported is True  # Default supported is True
        assert host.updates == []

    def test_host_connection(self, mocker, mock_connection):
        """
        Test the connection property of the Host object.
        """
        host = Host(
            name="test_host",
            ip="10.0.0.7",
            description="Test host",
            port=2222,
            username="test_user",
            connect_timeout=32,
        )

        _ = host.connection

        # Ensure the connection is created with the correct parameters
        mock_connection.assert_called_once_with(
            host=host.ip,
            port=host.port,
            user=host.username,
            connect_timeout=host.connect_timeout,
        )

    def test_host_connection_defaults(self, mocker, mock_connection):
        """
        Test the connection property of the Host object without
        optional parameters.
        """
        host = Host(
            name="test_host",
            ip="127.0.0.8",
        )

        _ = host.connection
        # Ensure the connection is created with default parameters
        mock_connection.assert_called_once_with(
            host=host.ip,
            port=22,  # Default port
            connect_timeout=10,  # Default connect timeout
        )

    def test_host_connection_global_username(
        self, mocker, mock_connection, mock_config_with_username
    ):
        """
        Test the connection property of the Host object with a global username.
        """
        host = Host(
            name="test_host",
            ip="127.0.0.8",
        )

        _ = host.connection

        mock_connection.assert_called_once_with(
            host=host.ip,
            port=22,  # Default port
            user="test_user",  # Global username from config
            connect_timeout=10,  # Default connect timeout
        )

    def test_host_connection_username_overrides_global(
        self, mocker, mock_connection, mock_config_with_username
    ):
        """
        Test the connection property of the Host object with a specific username
        and ensure it overrides the global username.
        """
        host = Host(
            name="test_host",
            ip="127.0.0.8",
            username="specific_user",  # Specific username
        )

        _ = host.connection
        mock_connection.assert_called_once_with(
            host=host.ip,
            port=22,  # Default port
            user="specific_user",  # Specific username overrides global
            connect_timeout=10,  # Default connect timeout
        )

    def test_host_config_sudo_policy(self, mocker):
        """
        Test that the Host object uses the sudo policy from the configuration.
        """
        host = Host(name="test_host", ip="127.0.0.8")

        assert host.sudo_policy == SudoPolicy.SKIP

    def test_host_config_sudo_policy_overrides_global(self, mocker):
        """
        Test that the Host object can override the global sudo policy
        with a specific one.
        """
        host = Host(name="test_host", ip="127.0.0.8", sudo_policy="nopasswd")

        assert host.sudo_policy == SudoPolicy.NOPASSWD

    def test_host_ping(self, mocker, mock_connection):
        """
        Functional test of the ping functionality for Host objects
        """
        # Mock successful run via context manager mock in fixture
        mock_instance = mock_connection.return_value
        mock_instance.run.return_value = mocker.Mock()
        mock_instance.run.return_value.failed = False
        mock_instance.is_connected = True

        host = Host(name="test_host", ip="127.0.0.1")
        assert host.ping() is True
        assert host.online is True

    def test_host_ping_raises_exception(self, mocker, mock_connection):
        """
        Test that ping raises an exception if the connection fails.
        """
        # Mock a failed run via context manager mock in fixture
        mock_instance = mock_connection.return_value
        mock_instance.run.side_effect = Exception("Super Test Suite Error")

        host = Host(name="test_host", ip="127.1.8.48")
        with pytest.raises(OfflineHostError, match="Super Test Suite Error"):
            host.ping(raise_on_error=True)

        assert host.online is False  # Should be False on failure

    def test_host_ping_rewords_shitty_paramiko_exception(self, mocker, mock_connection):
        """
        Test that ping rewrites the paramiko exception to be more helpful.

        For rationale, see:
        https://github.com/paramiko/paramiko/issues/387
        """
        from paramiko.ssh_exception import PasswordRequiredException

        mock_instance = mock_connection.return_value
        mock_instance.run.side_effect = PasswordRequiredException(
            "Private key file is encrypted."
        )

        host = Host(name="test_host", ip="127.0.0.8")

        with pytest.raises(OfflineHostError) as e:
            host.ping(raise_on_error=True)
            assert "private key file is encrypted" not in str(e).lower()
            assert "auth failure" in str(e).lower()

    @pytest.mark.parametrize(
        "exception_type", [TimeoutError, ConnectionError, Exception]
    )
    def test_host_ping_failure(self, mocker, mock_connection, exception_type):
        """
        Test of the failure cases for the ping functionality for Host objects
        """
        # Mock exception run via context manager mock in fixture
        mock_instance = mock_connection.return_value
        mock_instance.run.side_effect = exception_type("Connection failed")

        host = Host(name="test_host", ip="127.0.0.1")

        try:
            host.ping()
        except Exception as e:
            pytest.fail(f"Ping should not raise an exception, but we got a: {e}")

        assert host.online is False  # Should be False on failure

    def test_host_ping_failure_does_not_set_connection_timestamp(
        self, mocker, mock_connection
    ):
        """
        Test that failed ping does not set connection_last_used timestamp.

        This ensures that the ConnectionReaper doesn't treat failed connections
        as open connections that need to be reaped.
        """
        mock_instance = mock_connection.return_value
        mock_instance.run.side_effect = ConnectionError("Connection failed")
        mock_instance.is_connected = False

        host = Host(name="test_host", ip="127.0.0.1")
        host.ping()

        assert host.online is False
        assert host.connection_last_used is None

    def test_host_discovery(self, mocker, mock_connection, mock_hostinfo):
        """
        Functional test of the discover functionality for Host objects
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.discover()

        assert host.os == mock_hostinfo.os
        assert host.version == mock_hostinfo.version
        assert host.flavor == mock_hostinfo.flavor
        assert host.package_manager == mock_hostinfo.package_manager
        assert host.online is True

        # Ensure a Package Manager implementation was picked
        # in this case, with the fixture, it should be Apt
        assert host._pkginst is not None
        assert host._pkginst.__class__.__name__ == "Apt"

        # Ensure the connection was established
        mock_connection.assert_called_once_with(
            host=host.ip, port=host.port, connect_timeout=host.connect_timeout
        )

    def test_host_discovery_offline(self, mocker, mock_connection):
        """
        Test the discover functionality for Host objects when the host
        is offline.
        """
        # Mock platform_detect to also fail, since it is tried anyway
        mock_setup = mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=OfflineHostError("Platform detection also failed"),
        )

        # Mock ping failure with specific message
        host = Host(name="test_host", ip="127.0.0.1")
        mocker.patch.object(
            host, "ping", side_effect=OfflineHostError("Test Condition")
        )

        # Should raise the original ping error since both fail
        # Raising the platform_detect error here is unexpected.
        with pytest.raises(OfflineHostError, match="Test Condition"):
            host.discover()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False

        assert (
            mock_setup.call_count == 1
        )  # platform_detect will be called once even if ping fails

    def test_host_discovery_offline_after_ping(self, mocker, mock_connection):
        """
        Test the discovery functionality for Host objects when the
        host is offline and an exception is raised.
        """
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=OfflineHostError("Host is offline"),
        )

        host = Host(name="test_host", ip="127.0.0.1")
        mocker.patch.object(host, "ping", return_value=True)

        with pytest.raises(OfflineHostError):
            host.discover()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False

    def test_host_discovery_data_refresh_error(
        self, mocker, mock_connection, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test behavior of discovery when a DataRefreshError is raised.
        It should re-raise the exception and set the online status to False.
        """
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=DataRefreshError("Data refresh error"),
        )

        host = Host(name="test_host", ip="127.0.0.1")
        mocker.patch.object(host, "ping", return_value=True)

        with pytest.raises(DataRefreshError):
            host.discover()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False

    @pytest.mark.parametrize(
        "host_config,expected_repr",
        [
            (
                {"name": "test_host", "ip": "10.0.0.2", "port": 22},
                "Host(name='test_host', ip='10.0.0.2', port='22')",
            ),
            (
                {"name": "server1", "ip": "192.168.1.10"},
                "Host(name='server1', ip='192.168.1.10', port='22')",
            ),
            (
                {"name": "web_server", "ip": "172.16.0.5", "port": 8080},
                "Host(name='web_server', ip='172.16.0.5', port='8080')",
            ),
        ],
        ids=["basic", "default_port", "custom_port"],
    )
    def test_host_repr(self, host_config, expected_repr):
        """
        Test the string representation (__repr__) of the Host object.
        """
        host = Host(**host_config)
        assert repr(host) == expected_repr

    def test_security_update_property(self, mocker):
        """
        Test that security_updates property returns only updates marked as security.
        """
        # Create mock Update objects
        update1 = mocker.Mock(security=True)
        update2 = mocker.Mock(security=False)
        update3 = mocker.Mock(security=True)

        host = Host(name="test_host", ip="127.0.0.1")
        host.updates = [update1, update2, update3]

        result = host.security_updates

        assert update1 in result
        assert update3 in result
        assert update2 not in result
        assert all(u.security for u in result)
        assert len(result) == 2

    def test_security_updates_empty(self):
        """
        Test that security_updates property returns empty list if no updates.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        host.updates = []

        assert host.security_updates == []

    def test_is_stale_true_if_never_refreshed(self):
        """
        Test is_stale returns True if last_refresh is None.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        host.last_refresh = None

        assert host.is_stale is True

    def test_is_stale_true_if_past_threshold(self, mocker):
        """
        Test is_stale returns True if last_refresh is older than threshold.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        # Patch app config to set stale_threshold to 10 seconds
        mocker.patch(
            "exosphere.objects.app_config", {"options": {"stale_threshold": 10}}
        )

        # Set last_refresh to 20 seconds ago
        host.last_refresh = datetime.now(timezone.utc) - timedelta(seconds=20)

        assert host.is_stale is True

    def test_is_stale_false_if_within_threshold(self, mocker):
        """
        Test is_stale returns False if last_refresh is within threshold.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        # Patch app config to set stale_threshold to 60 seconds
        mocker.patch(
            "exosphere.objects.app_config", {"options": {"stale_threshold": 60}}
        )

        # Set last_refresh to 30 seconds ago
        host.last_refresh = datetime.now(timezone.utc) - timedelta(seconds=30)

        assert host.is_stale is False

    def test_is_stale_false_if_unsupported(self, mocker):
        """
        Test that unsupported hosts never return stale status
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = False

        mocker.patch(
            "exosphere.objects.app_config", {"options": {"stale_threshold": 60}}
        )

        host.last_refresh = datetime.now(timezone.utc) - timedelta(seconds=30)

        assert host.is_stale is False

    def test_to_dict(self, mock_config):
        """
        Test that to_dict() returns correct dictionary representation.

        Verifies that all expected fields are present with correct types
        and values for both complete and minimal host configurations.
        """
        mock_config.update_from_mapping({"options": {"stale_threshold": 86400}})

        # Test with fully populated host
        complete_host = Host(
            name="complete-host",
            ip="192.168.1.1",
            port=2222,
            description="Test host description",
        )
        complete_host.os = "linux"
        complete_host.flavor = "ubuntu"
        complete_host.version = "22.04"
        complete_host.package_manager = "apt"
        complete_host.last_refresh = datetime.now(timezone.utc)
        complete_host.supported = True
        complete_host.online = True
        complete_host.updates = [
            Update(
                name="curl",
                current_version="7.81.0-1",
                new_version="7.81.0-2",
                security=True,
                source="security",
            ),
        ]

        result = complete_host.to_dict()

        # Verify all required fields are present
        assert result["name"] == "complete-host"
        assert result["description"] == "Test host description"
        assert result["ip"] == "192.168.1.1"
        assert result["port"] == 2222
        assert result["os"] == "linux"
        assert result["flavor"] == "ubuntu"
        assert result["version"] == "22.04"
        assert result["supported"] is True
        assert result["stale"] is False  # Fresh host
        assert result["online"] is True
        assert result["package_manager"] == "apt"
        assert len(result["updates"]) == 1
        assert result["updates"][0]["name"] == "curl"
        assert isinstance(result["last_refresh"], str)  # ISO 8601 string
        assert result["last_refresh"].endswith("Z")  # UTC marker

        # Test with minimal/undiscovered host
        minimal_host = Host(name="minimal-host", ip="10.0.0.1")
        minimal_host.last_refresh = None  # Never refreshed

        minimal_result = minimal_host.to_dict()

        assert minimal_result["name"] == "minimal-host"
        assert minimal_result["description"] is None
        assert minimal_result["ip"] == "10.0.0.1"
        assert minimal_result["port"] == 22  # Default
        assert minimal_result["os"] is None  # Not discovered
        assert minimal_result["flavor"] is None
        assert minimal_result["version"] is None
        assert minimal_result["supported"] is True  # Default is True
        assert minimal_result["stale"] is True  # Never refreshed
        assert minimal_result["online"] is False  # Default
        assert minimal_result["package_manager"] is None
        assert minimal_result["updates"] == []
        assert minimal_result["last_refresh"] is None

        # Test stale detection with old last_refresh
        stale_host = Host(name="stale-host", ip="192.168.1.2")
        stale_host.last_refresh = datetime.now(timezone.utc) - timedelta(hours=25)
        stale_host.supported = True

        stale_result = stale_host.to_dict()
        assert stale_result["stale"] is True

    def test_sync_repos_success(
        self, mocker, mock_connection, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that sync_repos calls reposync and succeeds when online and _pkginst is set.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = True

        pkg_manager = mocker.Mock()
        pkg_manager.reposync.return_value = True

        host._pkginst = pkg_manager

        host.sync_repos()

        pkg_manager.reposync.assert_called_once_with(host.connection)

    def test_sync_repos_offline_raises(self, mock_config_with_sudopolicy_nopasswd):
        """
        Test that sync_repos raises OfflineHostError if host is offline.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = False

        with pytest.raises(OfflineHostError):
            host.sync_repos()

    def test_sync_repos_no_pkginst_raises(
        self, caplog, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that sync_repos raises DataRefreshError if _pkginst is None.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = True
        host._pkginst = None

        with pytest.raises(DataRefreshError):
            host.sync_repos()

        caplog.set_level("ERROR")
        logs = caplog.text
        assert "Package manager implementation unavailable" in logs

    def test_sync_repos_reposync_failure_raises(
        self, mocker, mock_connection, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that sync_repos raises DataRefreshError if reposync returns False.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True

        pkg_manager = mocker.Mock()
        pkg_manager.reposync.return_value = False

        host._pkginst = pkg_manager

        with pytest.raises(DataRefreshError):
            host.sync_repos()

    def test_sync_repos_sudopolicy_disallowed(self, mocker, mock_connection, caplog):
        """
        Test that sync_repos skips the task if sudo policy disallows it
        """

        @requires_sudo
        def reposync(cx):
            raise AssertionError("Should not be called!")

        mock_pkg = mocker.Mock()
        mock_pkg.reposync = mocker.Mock(side_effect=reposync)

        host = Host(name="test_host", ip="127.0.0.1", sudo_policy=SudoPolicy.SKIP)
        host.online = True
        host.supported = True

        host._pkginst = mock_pkg

        with caplog.at_level("WARNING"):
            result = host.sync_repos()

        assert result is None
        mock_pkg.reposync.assert_not_called()
        assert (
            "Skipping package repository sync on test_host due to SudoPolicy: skip"
            in caplog.text
        )

    def test_refresh_updates_success_with_updates(
        self, mocker, mock_connection, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that refresh_updates populates updates and sets last_refresh when updates are found.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = True

        pkg_manager = mocker.Mock()
        updates_list = [mocker.Mock(), mocker.Mock()]

        pkg_manager.get_updates.return_value = updates_list
        host._pkginst = pkg_manager

        before = datetime.now(timezone.utc)
        host.refresh_updates()
        after = datetime.now(timezone.utc)

        pkg_manager.get_updates.assert_called_once_with(host.connection)
        assert host.updates == updates_list
        assert host.last_refresh is not None
        assert before <= host.last_refresh <= after

    def test_refresh_updates_success_no_updates(
        self, mocker, mock_connection, caplog, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that refresh_updates logs info when no updates are found.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = True

        pkg_manager = mocker.Mock()
        pkg_manager.get_updates.return_value = []
        host._pkginst = pkg_manager

        caplog.set_level("INFO")
        host.refresh_updates()

        assert host.updates == []
        assert "No updates available for test_host" in caplog.text

    def test_refresh_updates_offline_raises(
        self, mocker, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that refresh_updates raises OfflineHostError if host is offline.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = False
        host._pkginst = mocker.Mock()

        with pytest.raises(OfflineHostError):
            host.refresh_updates()

    def test_refresh_updates_no_pkginst_raises(
        self, mocker, caplog, mock_config_with_sudopolicy_nopasswd
    ):
        """
        Test that refresh_updates raises DataRefreshError if _pkginst is None.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = True
        host._pkginst = None

        caplog.set_level("ERROR")

        with pytest.raises(DataRefreshError):
            host.refresh_updates()

        assert "Package manager implementation unavailable" in caplog.text

    def test_refresh_updates_sudopolicy_disallowed(
        self, mocker, mock_connection, caplog
    ):
        """
        Test that refresh_updates skips the task if sudo policy disallows it
        """

        @requires_sudo
        def get_updates(cx):
            raise AssertionError("Should not be called!")

        mock_pkg = mocker.Mock()
        mock_pkg.get_updates = mocker.Mock(side_effect=get_updates)

        host = Host(name="test_host", ip="127.0.0.8", sudo_policy=SudoPolicy.SKIP)
        host.online = True
        host.supported = True

        host._pkginst = mock_pkg

        with caplog.at_level("WARNING"):
            result = host.refresh_updates()

        assert result is None
        mock_pkg.get_updates.assert_not_called()
        assert (
            "Skipping updates refresh on test_host due to SudoPolicy: skip"
            in caplog.text
        )

    def test_host_discovery_unsupported_os(self, mocker, mock_connection):
        """
        Test that discover preserves online status for unsupported OS
        but marks host as unsupported
        """
        from exosphere.data import HostInfo

        # Mock platform_detect to return HostInfo with is_supported=False
        unsupported_host_info = HostInfo(
            os="exotic-os",
            version=None,
            flavor=None,
            package_manager=None,
            is_supported=False,
        )
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            return_value=unsupported_host_info,
        )

        host = Host(name="test_host", ip="127.0.0.1")

        # Mock ping to set online status to True and return True
        def mock_ping(raise_on_error=False, close_connection=True):
            host.online = True
            return True

        mocker.patch.object(host, "ping", side_effect=mock_ping)

        # discover() should complete without raising an exception
        host.discover()

        # Host should remain online but be marked as unsupported
        assert host.online is True
        assert host.supported is False

        # Platform info should reflect the HostInfo returned
        assert host.os == "exotic-os"  # OS should be populated
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None
        assert host._pkginst is None

    def test_host_discovery_non_unix_system(self, mocker, mock_connection):
        """
        Test that discover raises UnsupportedOSError for non-Unix systems
        where uname -s fails
        """
        from exosphere.errors import UnsupportedOSError

        # Mock platform_detect to raise UnsupportedOSError for non-Unix systems
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=UnsupportedOSError(
                "Unable to detect OS: 'uname -s' command failed. "
                "This likely indicates a non-Unix-like system which is not supported by Exosphere."
            ),
        )

        host = Host(name="test_host", ip="127.0.0.1")

        # Mock ping to set online status to True and return True
        def mock_ping(raise_on_error=False, close_connection=True):
            host.online = True
            return True

        mocker.patch.object(host, "ping", side_effect=mock_ping)

        # discover() should raise UnsupportedOSError and mark host as online but unsupported
        with pytest.raises(UnsupportedOSError, match="Unable to detect OS"):
            host.discover()

        # Host should be marked as offline in this failure case
        assert host.online is False

    def test_host_discovery_auth_error_priority(self, mocker, mock_connection):
        """
        Test that UnsupportedOSError from platform detection takes precedence
        when it provides more specific information than ping failures
        """
        from exosphere.errors import OfflineHostError, UnsupportedOSError

        # Mock platform_detect to raise UnsupportedOSError
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=UnsupportedOSError("Unable to detect OS"),
        )

        host = Host(name="test_host", ip="127.0.0.1")

        # Mock ping to raise an authentication error with the friendly message
        auth_error = OfflineHostError(
            "Auth Failure. "
            "Verify that keypair authentication is enabled on the server "
            "and that your agent is running with the correct keys loaded."
        )
        mocker.patch.object(host, "ping", side_effect=auth_error)

        # discover() should raise the UnsupportedOSError as it provides more specific info
        with pytest.raises(UnsupportedOSError, match="Unable to detect OS"):
            host.discover()

    @pytest.mark.parametrize(
        "method_name, expected_warning",
        [
            ("refresh_updates", "Update refresh is not available."),
            ("sync_repos", "Repository sync is not available"),
        ],
        ids=["refresh_updates", "sync_repos"],
    )
    def test_unsupported_host_operations(
        self, mocker, caplog, method_name, expected_warning
    ):
        """
        Test that operations on unsupported hosts log appropriate warnings
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host.supported = False

        with caplog.at_level("WARNING"):
            method = getattr(host, method_name)
            method()

        assert expected_warning in caplog.text

    @pytest.mark.parametrize(
        "host_state,expected_status,expected_platform",
        [
            # Online supported host
            (
                {
                    "online": True,
                    "supported": True,
                    "os": "Ubuntu",
                    "version": "22.04",
                    "flavor": "Server",
                    "package_manager": "apt",
                },
                "Online",
                "Ubuntu, 22.04, Server, apt",
            ),
            # Online unsupported host
            (
                {
                    "online": True,
                    "supported": False,
                    "os": None,
                    "version": None,
                    "flavor": None,
                    "package_manager": None,
                },
                "Online (Unsupported)",
                "None, None, None, None",
            ),
            # Offline supported host (discovered)
            (
                {
                    "online": False,
                    "supported": True,
                    "os": "Debian",
                    "version": "11",
                    "flavor": "Bullseye",
                    "package_manager": "apt",
                },
                "Offline",
                "Debian, 11, Bullseye, apt",
            ),
            # Offline undiscovered host
            (
                {
                    "online": False,
                    "supported": True,
                    "os": None,
                    "version": None,
                    "flavor": None,
                    "package_manager": None,
                },
                "Offline",
                "None, None, None, None",
            ),
        ],
        ids=[
            "online_supported",
            "online_unsupported",
            "offline_supported",
            "offline_undiscovered",
        ],
    )
    def test_host_string_representation(
        self, host_state, expected_status, expected_platform
    ):
        """
        Test the string representation (__str__) shows different host states correctly
        """
        host = Host(name="test_host", ip="127.0.0.1")

        # Set host state
        for attr, value in host_state.items():
            setattr(host, attr, value)

        result = str(host)

        # Verify the expected status and platform info are in the result
        assert expected_status in result
        assert expected_platform in result

        # For unsupported hosts, ensure we don't show repeated "Unsupported" text
        if not host_state["supported"]:
            assert "Unsupported, Unsupported, Unsupported, Unsupported" not in result

    def test_host_initialization_supported_defaults(self):
        """
        Test that new hosts default to supported until discovery
        """
        host = Host(name="test_host", ip="127.0.0.1")
        assert host.supported is True

    def test_host_close_without_connection(self, mocker):
        """
        Test close() when no connection exists.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        # There should not be any exceptions here.
        host.close()
        host.close(clear=True)

    def test_host_close_with_connection(self, mocker, mock_connection):
        """
        Test close() when a connection exists.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        _ = host.connection

        # Verify connection was created
        assert host.connection_last_used is not None

        host.close()

        mock_connection.return_value.close.assert_called_once()
        assert host.connection_last_used is None

        # Connection object should still exist (clear=False by default)
        # Accessing connection again should work without creating a new one
        _ = host.connection
        assert mock_connection.call_count == 1

    def test_host_close_with_clear(self, mocker, mock_connection):
        """
        Test that close(clear=True) removes the connection object.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        _ = host.connection

        host.close(clear=True)

        mock_connection.return_value.close.assert_called_once()
        assert host.connection_last_used is None

        # Accessing connection again should create a new one
        _ = host.connection
        assert mock_connection.call_count == 2

    def test_host_close_handles_exception(self, mocker, mock_connection, caplog):
        """
        Test that close() handles exceptions gracefully.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        _ = host.connection
        mock_connection.return_value.close.side_effect = Exception("Test error")

        host.close()

        assert "Error closing connection" in caplog.text
        assert host.connection_last_used is None

    def test_host_connection_thread_safety(self, mocker, mock_connection):
        """
        Test that connection property is protected by lock.
        """
        import threading

        host = Host(name="test_host", ip="127.0.0.1")
        connections = []

        def get_connection():
            connections.append(host.connection)

        # Create multiple threads accessing connection simultaneously
        threads = [threading.Thread(target=get_connection) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same connection object
        assert len(set(id(c) for c in connections)) == 1

        # Connection should only be created once
        assert mock_connection.call_count == 1

    def test_host_close_thread_safety(self, mocker, mock_connection):
        """
        Test that close() is protected by lock and handles concurrent calls.
        """
        import threading

        host = Host(name="test_host", ip="127.0.0.1")

        # Create connection
        _ = host.connection

        # Close from multiple threads simultaneously
        threads = [threading.Thread(target=lambda: host.close()) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # The lock ensures that close operations don't conflict
        # Multiple calls may occur but the connection should be closed
        assert mock_connection.return_value.close.called
        assert host.connection_last_used is None

    def test_host_connection_updates_last_used(self, mocker, mock_connection):
        """
        Test that accessing connection updates the last_used timestamp.
        """
        import time

        host = Host(name="test_host", ip="127.0.0.1")

        before = time.time()

        _ = host.connection

        after = time.time()

        assert host.connection_last_used is not None
        assert before <= host.connection_last_used <= after

        time.sleep(0.01)
        first_timestamp = host.connection_last_used

        _ = host.connection

        assert host.connection_last_used > first_timestamp

    def test_is_connected_returns_true_when_connected(self, mocker, mock_connection):
        """Test that is_connected returns True when connection is established."""
        mock_instance = mock_connection.return_value
        mock_instance.is_connected = True

        host = Host(name="test_host", ip="127.0.0.1")
        _ = host.connection  # Create connection

        assert host.is_connected is True

    def test_is_connected_returns_false_when_no_connection(self, mocker):
        """Test that is_connected returns False when connection doesn't exist."""
        host = Host(name="test_host", ip="127.0.0.1")

        assert host.is_connected is False

    def test_is_connected_returns_false_when_not_connected(
        self, mocker, mock_connection
    ):
        """Test that is_connected returns False when connection exists but not connected."""
        mock_instance = mock_connection.return_value
        mock_instance.is_connected = False

        host = Host(name="test_host", ip="127.0.0.1")
        _ = host.connection  # Create connection object

        assert host.is_connected is False

    def test_connection_last_used_returns_none_when_not_connected(
        self, mocker, mock_connection
    ):
        """Test that connection_last_used returns None when not connected."""
        mock_instance = mock_connection.return_value
        mock_instance.is_connected = False

        host = Host(name="test_host", ip="127.0.0.1")
        _ = host.connection  # Sets timestamp

        # Should return None because is_connected is False
        assert host.connection_last_used is None

    def test_connection_last_used_warns_on_desync(
        self, mocker, mock_connection, caplog
    ):
        """Test that connection_last_used logs warning when desynchronized."""
        import logging

        mock_instance = mock_connection.return_value
        mock_instance.is_connected = False

        host = Host(name="test_host", ip="127.0.0.1")
        _ = host.connection  # Sets timestamp

        with caplog.at_level(logging.WARNING):
            _ = host.connection_last_used

        assert "Connection to test_host no longer active" in caplog.text
        assert "resetting last used" in caplog.text

    def test_connection_last_used_returns_timestamp_when_connected(
        self, mocker, mock_connection
    ):
        """Test that connection_last_used returns timestamp when connected."""
        import time

        mock_instance = mock_connection.return_value
        mock_instance.is_connected = True

        host = Host(name="test_host", ip="127.0.0.1")

        before = time.time()
        _ = host.connection
        after = time.time()

        last_used = host.connection_last_used
        assert last_used is not None
        assert before <= last_used <= after


class TestHostStateSerialization:
    """Test suite for Host and HostState serialization"""

    def test_to_state_basic(self, mocker):
        """Test basic conversion from Host to HostState"""
        from exosphere.data import HostState

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.version = "12"
        host.flavor = "debian"
        host.package_manager = "apt"
        host.supported = True
        host.online = True
        host.updates = []
        host.last_refresh = None

        state = host.to_state()

        assert isinstance(state, HostState)
        assert state.os == "linux"
        assert state.version == "12"
        assert state.flavor == "debian"
        assert state.package_manager == "apt"
        assert state.supported is True
        assert state.online is True
        assert isinstance(state.updates, tuple)
        assert len(state.updates) == 0
        assert state.last_refresh is None

    def test_to_state_with_updates(self, mocker):
        """Test conversion with updates list"""
        from exosphere.data import Update

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.supported = True
        host.online = True
        host.updates = [
            Update(
                name="pkg1", current_version="1.0", new_version="1.1", security=False
            ),
            Update(
                name="pkg2", current_version="2.0", new_version="2.1", security=True
            ),
        ]
        host.last_refresh = datetime.now(timezone.utc)

        state = host.to_state()

        assert isinstance(state.updates, tuple)
        assert len(state.updates) == 2
        assert state.updates[0].name == "pkg1"
        assert state.updates[1].name == "pkg2"
        assert state.updates[1].security is True

    def test_to_state_with_timezone_aware_datetime(self, mocker):
        """Test conversion preserves timezone-aware datetime"""
        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.supported = True
        host.online = True
        host.updates = []

        now = datetime.now(timezone.utc)
        host.last_refresh = now

        state = host.to_state()

        assert state.last_refresh == now
        assert state.last_refresh.tzinfo == timezone.utc  # type: ignore

    def test_from_state_basic(self, mocker):
        """Test basic loading of state into Host"""
        from exosphere.data import HostState

        host = Host(name="test_host", ip="127.0.0.1")

        state = HostState(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        host.from_state(state)

        assert host.os == "linux"
        assert host.version == "12"
        assert host.flavor == "debian"
        assert host.package_manager == "apt"
        assert host.supported is True
        assert host.online is True
        assert isinstance(host.updates, list)
        assert len(host.updates) == 0

    def test_from_state_converts_tuple_to_list(self, mocker):
        """Test that from_state converts updates tuple to list"""
        from exosphere.data import HostState, Update

        host = Host(name="test_host", ip="127.0.0.1")

        update1 = Update(
            name="libhyperoneechan",
            current_version="1.0",
            new_version="1.1",
            security=False,
        )
        update2 = Update(
            name="lillies-bloom",
            current_version="2.0",
            new_version="2.1",
            security=True,
        )

        state = HostState(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
            supported=True,
            online=True,
            updates=(update1, update2),
            last_refresh=None,
        )

        host.from_state(state)

        assert isinstance(host.updates, list)
        assert len(host.updates) == 2
        assert host.updates[0] == update1
        assert host.updates[1] == update2

    def test_from_state_recreates_pkginst(self, mocker):
        """Test that from_state recreates package manager instance"""
        from exosphere.data import HostState

        mock_factory = mocker.patch("exosphere.objects.PkgManagerFactory.create")
        fake_pkginst = mocker.MagicMock()
        mock_factory.return_value = fake_pkginst

        host = Host(name="test_host", ip="127.0.0.1")

        state = HostState(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        host.from_state(state)

        mock_factory.assert_called_once_with("apt")
        assert host._pkginst == fake_pkginst

    def test_from_state_no_pkginst_when_not_supported(self, mocker):
        """Test that from_state doesn't create pkginst for unsupported hosts"""
        from exosphere.data import HostState

        mock_factory = mocker.patch("exosphere.objects.PkgManagerFactory.create")

        host = Host(name="test_host", ip="127.0.0.1")

        state = HostState(
            os="linux",
            version="12",
            flavor="unknown",
            package_manager="unknown",
            supported=False,
            online=True,
            updates=(),
            last_refresh=None,
        )

        host.from_state(state)

        mock_factory.assert_not_called()
        assert host._pkginst is None

    def test_from_state_warns_on_newer_schema_version(self, mocker, caplog):
        """Test that from_state warns when loading newer schema version"""
        from exosphere.data import HostState

        host = Host(name="test_host", ip="127.0.0.1")

        state = HostState(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
            schema_version=999,  # Future version
        )

        with caplog.at_level("WARNING"):
            host.from_state(state)

        assert any(
            "HostState schema version 999 is newer" in message
            for message in caplog.messages
        )

    def test_roundtrip_preserves_data(self, mocker):
        """Verify Host → HostState → Host preserves all data"""
        from exosphere.data import Update

        # Create host with full state
        host1 = Host(name="test_host", ip="127.0.0.1")
        host1.os = "linux"
        host1.version = "12"
        host1.flavor = "debian"
        host1.package_manager = "apt"
        host1.supported = True
        host1.online = True
        host1.updates = [
            Update(
                name="pkg1", current_version="1.0", new_version="1.1", security=False
            ),
            Update(
                name="pkg2", current_version="2.0", new_version="2.1", security=True
            ),
        ]
        host1.last_refresh = datetime(2026, 1, 6, 10, 30, 0, tzinfo=timezone.utc)

        # Serialize to state
        state = host1.to_state()

        # Create new host and deserialize
        host2 = Host(name="test_host", ip="127.0.0.1")
        host2.from_state(state)

        # Verify all data preserved
        assert host2.os == "linux"
        assert host2.version == "12"
        assert host2.flavor == "debian"
        assert host2.package_manager == "apt"
        assert host2.supported is True
        assert host2.online is True
        assert len(host2.updates) == 2
        assert host2.updates[0].name == "pkg1"
        assert host2.updates[1].name == "pkg2"
        assert host2.updates[1].security is True
        assert host2.last_refresh == datetime(
            2026, 1, 6, 10, 30, 0, tzinfo=timezone.utc
        )

    def test_roundtrip_with_minimal_state(self, mocker):
        """Verify round-trip works with minimal state"""
        host1 = Host(name="test_host", ip="127.0.0.1")
        # Don't set any discovery state, use defaults

        state = host1.to_state()

        host2 = Host(name="test_host", ip="127.0.0.1")
        host2.from_state(state)

        assert host2.os is None
        assert host2.version is None
        assert host2.flavor is None
        assert host2.package_manager is None
        assert host2.supported is True  # Default
        assert host2.online is False  # Default
        assert len(host2.updates) == 0
        assert host2.last_refresh is None


class TestHostTaskMethodsConnectionCleanup:
    """Tests that Host task methods properly close connections based on config."""

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_discover_connection_cleanup(
        self, mocker, ssh_pipelining, mock_connection, mock_hostinfo
    ):
        """Test discover() closes connection when pipelining disabled."""

        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True

        # Mock close method to track calls
        mock_close = mocker.patch.object(host, "close")

        # Mock PkgManagerFactory
        mocker.patch("exosphere.objects.PkgManagerFactory")

        host.discover()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_ping_connection_cleanup(self, mocker, ssh_pipelining, mock_connection):
        """Test ping() respects close_connection parameter."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")

        # Mock close method
        mock_close = mocker.patch.object(host, "close")

        # Configure mock connection for ping
        mock_connection.return_value.run = mocker.Mock()

        # ping() now checks ssh_pipelining internally
        host.ping()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_sync_repos_connection_cleanup(
        self, mocker, ssh_pipelining, mock_connection
    ):
        """Test sync_repos() closes connection when pipelining disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True
        host.supported = True

        # Mock close method
        mock_close = mocker.patch.object(host, "close")

        # Mock package manager
        mock_pkg = mocker.Mock()
        mock_pkg.reposync = mocker.Mock(return_value=True)
        host._pkginst = mock_pkg
        host.sudo_policy = SudoPolicy.NOPASSWD

        # Mock check_sudo_policy to return True
        mocker.patch("exosphere.objects.check_sudo_policy", return_value=True)

        host.sync_repos()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_refresh_updates_connection_cleanup(
        self, mocker, ssh_pipelining, mock_connection
    ):
        """Test refresh_updates() closes connection when pipelining disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True
        host.supported = True

        mock_close = mocker.patch.object(host, "close")

        mock_pkg = mocker.Mock()
        mock_pkg.get_updates = mocker.Mock(return_value=[])
        host._pkginst = mock_pkg
        host.sudo_policy = SudoPolicy.NOPASSWD

        mocker.patch("exosphere.objects.check_sudo_policy", return_value=True)

        host.refresh_updates()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_discover_connection_cleanup_on_exception(
        self, mocker, ssh_pipelining, mock_connection
    ):
        """Test discover() closes connection on exception when pipelining disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True

        # Mock close method
        mock_close = mocker.patch.object(host, "close")

        # Mock platform_detect to raise exception
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=DataRefreshError("Test error"),
        )

        # Mock ping to not raise
        mocker.patch.object(host, "ping", return_value=True)

        with pytest.raises(DataRefreshError):
            host.discover()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_sync_repos_connection_cleanup_on_exception(
        self, mocker, ssh_pipelining, mock_connection
    ):
        """Test sync_repos() closes connection on exception when pipelining disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True
        host.supported = True

        # Mock close method
        mock_close = mocker.patch.object(host, "close")

        # Mock package manager to raise exception
        mock_pkg = mocker.Mock()
        mock_pkg.reposync = mocker.Mock(side_effect=RuntimeError("Test error"))
        host._pkginst = mock_pkg
        host.sudo_policy = SudoPolicy.NOPASSWD

        mocker.patch("exosphere.objects.check_sudo_policy", return_value=True)

        with pytest.raises(RuntimeError):
            host.sync_repos()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()

    @pytest.mark.parametrize(
        "ssh_pipelining", [True, False], ids=["pipelining_on", "pipelining_off"]
    )
    def test_refresh_updates_connection_cleanup_on_exception(
        self, mocker, ssh_pipelining, mock_connection
    ):
        """Test refresh_updates() closes connection on exception when pipelining disabled."""
        config = Configuration()
        config["options"]["ssh_pipelining"] = ssh_pipelining
        mocker.patch("exosphere.objects.app_config", config)

        host = Host(name="test", ip="127.0.0.1")
        host.online = True
        host.supported = True

        # Mock close method
        mock_close = mocker.patch.object(host, "close")

        # Mock package manager to raise exception
        mock_pkg = mocker.Mock()
        mock_pkg.get_updates = mocker.Mock(side_effect=RuntimeError("Test error"))
        host._pkginst = mock_pkg
        host.sudo_policy = SudoPolicy.NOPASSWD

        mocker.patch("exosphere.objects.check_sudo_policy", return_value=True)

        with pytest.raises(RuntimeError):
            host.refresh_updates()

        if ssh_pipelining:
            mock_close.assert_not_called()
        else:
            mock_close.assert_called_once()
