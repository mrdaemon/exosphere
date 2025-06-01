from datetime import datetime, timedelta

import pytest

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

    def test_host_initialization(self):
        """
        Test the initialization of the Host object.
        """
        host = Host(name="test_host", ip="172.16.64.10", port=22)

        assert host.name == "test_host"
        assert host.ip == "172.16.64.10"
        assert host.port == 22

        assert host.online is False

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
        mock_connection.assert_called_once_with(host=host.ip, port=host.port)

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
