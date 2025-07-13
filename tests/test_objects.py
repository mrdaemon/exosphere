from datetime import datetime, timedelta

import pytest

from exosphere.config import Configuration
from exosphere.data import HostInfo
from exosphere.errors import DataRefreshError, OfflineHostError
from exosphere.objects import Host


class TestHostObject:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        return mocker.patch("exosphere.objects.Connection", autospec=True)

    @pytest.fixture
    def mock_hostinfo(self, mocker):
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
        )

        mocker.patch("exosphere.setup.detect.platform_detect", return_value=hostinfo)

        return hostinfo

    @pytest.fixture
    def mock_config_with_username(self, mocker):
        """
        Fixture to mock the application configuration with all its
        default values, but also includes a set default_username.
        """

        # Create a fresh configuration object with defaults
        config = Configuration()

        # Set a default username for testing
        config["options"]["default_username"] = "test_user"

        # Patch the app_config to return this configuration
        return mocker.patch("exosphere.objects.app_config", config)

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
        )

        assert host.name == "test_host"
        assert host.ip == "172.16.64.10"
        assert host.port == 2222
        assert host.connect_timeout == 32
        assert host.username == "test_user"
        assert host.description == "Test host"

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

    def test_host_ping(self, mocker, mock_connection):
        """
        Functional test of the ping functionality for Host objects
        """
        mock_connection.run.return_value = mocker.Mock()
        mock_connection.run.return_value.failed = False

        host = Host(name="test_host", ip="127.0.0.1")
        assert host.ping() is True
        assert host.online is True

    @pytest.mark.parametrize(
        "exception_type", [TimeoutError, ConnectionError, Exception]
    )
    def test_host_ping_failure(self, mocker, mock_connection, exception_type):
        """
        Test of the failure cases for the ping functionality for Host objects
        """
        mock_connection.return_value.run.side_effect = exception_type(
            "Connection failed"
        )

        host = Host(name="test_host", ip="127.0.0.1")

        try:
            host.ping()
        except Exception as e:
            pytest.fail(f"Ping should not raise an exception, but we got a: {e}")

        assert host.online is False  # Should be False on failure

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
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=OfflineHostError("Host is offline"),
        )

        host = Host(name="test_host", ip="127.0.0.1")
        mocker.patch.object(host, "ping", return_value=False)

        host.discover()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False

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

        host.discover()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False

    def test_host_discovery_data_refresh_error(self, mocker, mock_connection):
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

    def test_host_repr(self):
        """
        Test the string representation of the Host object.
        """
        host = Host(name="test_host", ip="10.0.0.2", port=22)
        assert repr(host) == "Host(name='test_host', ip='10.0.0.2', port='22')"

    def test_host_getstate_removes_unserializables(self, mocker):
        """
        Test that __getstate__ removes unserializable attributes.
        """
        host = Host(name="test_host", ip="127.0.0.1")

        mocker.patch.object(host, "_connection", mocker.Mock())
        mocker.patch.object(host, "_pkginst", mocker.Mock())

        state = host.__getstate__()

        assert state["_connection"] is None
        assert state["_pkginst"] is None

        assert state["name"] == "test_host"
        assert state["ip"] == "127.0.0.1"

    def test_host_setstate_restores_state_and_pkginst(self, mocker):
        """
        Test that __setstate__ restores state and recreates _pkginst
        """
        fake_pkginst = mocker.MagicMock()
        mock_factory = mocker.patch(
            "exosphere.objects.PkgManagerFactory.create", return_value=fake_pkginst
        )

        state = {
            "name": "test_host",
            "ip": "127.0.0.1",
            "port": 22,
            "online": True,
            "os": "linux",
            "version": "12",
            "flavor": "debian",
            "package_manager": "apt",
            "_connection": "THE BEFORES",
            "_pkginst": "THE BEFORES",
            "updates": [],
            "last_refresh": None,
        }

        host = Host(name="test_host", ip="127.0.0.1")
        host.__setstate__(state)

        assert host.name == "test_host"
        assert host.ip == "127.0.0.1"
        assert host.os == "linux"
        assert host.version == "12"
        assert host.package_manager == "apt"

        assert host._connection != "THE BEFORES"
        assert host._connection != "THE BEFORES"

        assert host._connection is None
        mock_factory.assert_called_once_with("apt")
        assert host._pkginst == fake_pkginst

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
        host.last_refresh = datetime.now() - timedelta(seconds=20)

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
        host.last_refresh = datetime.now() - timedelta(seconds=30)

        assert host.is_stale is False

    def test_refresh_catalog_success(self, mocker, mock_connection):
        """
        Test that refresh_catalog calls reposync and succeeds when online and _pkginst is set.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True

        pkg_manager = mocker.MagicMock()
        pkg_manager.reposync.return_value = True

        host._pkginst = pkg_manager

        host.refresh_catalog()

        pkg_manager.reposync.assert_called_once_with(host.connection)

    def test_refresh_catalog_offline_raises(self):
        """
        Test that refresh_catalog raises OfflineHostError if host is offline.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = False

        with pytest.raises(OfflineHostError):
            host.refresh_catalog()

    def test_refresh_catalog_no_pkginst_raises(self, caplog):
        """
        Test that refresh_catalog raises DataRefreshError if _pkginst is None.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host._pkginst = None

        with pytest.raises(DataRefreshError):
            host.refresh_catalog()

        caplog.set_level("ERROR")
        logs = caplog.text
        assert "Package manager implementation unavailable" in logs

    def test_refresh_catalog_reposync_failure_raises(self, mocker, mock_connection):
        """
        Test that refresh_catalog raises DataRefreshError if reposync returns False.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True

        pkg_manager = mocker.Mock()
        pkg_manager.reposync.return_value = False

        host._pkginst = pkg_manager

        with pytest.raises(DataRefreshError):
            host.refresh_catalog()

    def test_refresh_updates_success_with_updates(self, mocker, mock_connection):
        """
        Test that refresh_updates populates updates and sets last_refresh when updates are found.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True

        pkg_manager = mocker.Mock()
        updates_list = [mocker.Mock(), mocker.Mock()]

        pkg_manager.get_updates.return_value = updates_list
        host._pkginst = pkg_manager

        before = datetime.now()
        host.refresh_updates()
        after = datetime.now()

        pkg_manager.get_updates.assert_called_once_with(host.connection)
        assert host.updates == updates_list
        assert host.last_refresh is not None
        assert before <= host.last_refresh <= after

    def test_refresh_updates_success_no_updates(self, mocker, mock_connection, caplog):
        """
        Test that refresh_updates logs info when no updates are found.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True

        pkg_manager = mocker.Mock()
        pkg_manager.get_updates.return_value = []
        host._pkginst = pkg_manager

        caplog.set_level("INFO")
        host.refresh_updates()

        assert host.updates == []
        assert "No updates available for test_host" in caplog.text

    def test_refresh_updates_offline_raises(self, mocker):
        """
        Test that refresh_updates raises OfflineHostError if host is offline.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = False
        host._pkginst = mocker.Mock()

        with pytest.raises(OfflineHostError):
            host.refresh_updates()

    def test_refresh_updates_no_pkginst_raises(self, mocker, caplog):
        """
        Test that refresh_updates raises DataRefreshError if _pkginst is None.
        """
        host = Host(name="test_host", ip="127.0.0.1")
        host.online = True
        host._pkginst = None

        caplog.set_level("ERROR")

        with pytest.raises(DataRefreshError):
            host.refresh_updates()

        assert "Package manager implementation unavailable" in caplog.text
