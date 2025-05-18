import pytest

from exosphere.data import HostInfo
from exosphere.errors import OfflineHostError
from exosphere.objects import Host


class TestHostObject:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        return mocker.patch("exosphere.objects.Connection", autospec=True)

    def test_host_initialization(self):
        host = Host(name="test_host", ip="172.16.64.10", port=22)

        assert host.name == "test_host"
        assert host.ip == "172.16.64.10"
        assert host.port == 22

    def test_host_ping(self, mocker, mock_connection):
        mock_connection.run.return_value = mocker.Mock()
        mock_connection.run.return_value.failed = False

        host = Host(name="test_host", ip="127.0.0.1")
        host.ping()

        assert host.online is True

    @pytest.mark.parametrize(
        "exception_type", [TimeoutError, ConnectionError, Exception]
    )
    def test_host_ping_failure(self, mocker, mock_connection, exception_type):
        mock_connection.return_value.run.side_effect = exception_type(
            "Connection failed"
        )

        host = Host(name="test_host", ip="127.0.0.1")

        try:
            host.ping()
        except Exception as e:
            pytest.fail(f"Ping should not raise an exception, but we got a: {e}")

        assert host.online is False  # Should be False on failure

    def test_host_sync(self, mocker, mock_connection):
        mock_hostinfo = HostInfo(
            os="linux",
            version="jessie",
            flavor="debian",
            package_manager="apt",
        )

        mocker.patch(
            "exosphere.setup.detect.platform_detect", return_value=mock_hostinfo
        )
        host = Host(name="test_host", ip="127.0.0.1")
        host.sync()

        assert host.os == "linux"
        assert host.version == "jessie"
        assert host.flavor == "debian"
        assert host.package_manager == "apt"
        assert host.online is True

        # Ensure the connection was established
        mock_connection.assert_called_once_with(host=host.ip, port=host.port)

    def test_host_sync_offline(self, mocker, mock_connection):
        mocker.patch(
            "exosphere.setup.detect.platform_detect",
            side_effect=OfflineHostError("Host is offline"),
        )

        host = Host(name="test_host", ip="127.0.0.1")
        host.sync()

        assert host.os is None
        assert host.version is None
        assert host.flavor is None
        assert host.package_manager is None

        assert host.online is False
