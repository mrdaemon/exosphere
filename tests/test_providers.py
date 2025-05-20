import pytest

from exosphere.data import Update
from exosphere.providers import Apt


class TestAptProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx = mocker.patch("exosphere.providers.debian.Connection", autospec=True)
        mock_cx.run.return_value.failed = False
        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value.failed = True
        return mock_connection

    @pytest.fixture
    def mock_pkg_output(self, mocker, mock_connection):
        """
        Fixture to mock the output of the apt command enumerating packages.
        """
        output = """
        
        Inst base-files [12.4+deb12u10] (12.4+deb12u11 Debian:12.11/stable [arm64])
        Inst bash [5.2.15-2+b7] (5.2.15-2+b8 Debian:12.11/stable [arm64])
        Inst login [1:4.13+dfsg1-1+b1] (1:4.13+dfsg1-1+deb12u1 Debian:12.11/stable [arm64])

        Inst passwd [1:4.13+dfsg1-1+b1] (1:4.13+dfsg1-1+deb12u1 Debian:12.11/stable [arm64])
        Inst initramfs-tools [0.142+rpt3+deb12u1] (0.142+rpt3+deb12u3 Raspberry Pi Foundation:stable [all])
        Inst big-patch [1.0-1] (1.0-2 Debian:12.11/bookworm-security [arm64])
        """
        mock_connection.run.return_value.stdout = output
        return mock_connection

    @pytest.mark.parametrize(
        "connection_fixture, expected",
        [
            ("mock_connection", True),
            ("mock_connection_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, mocker, request, connection_fixture, expected):
        """
        Test the reposync method of the Apt provider.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        apt = Apt()
        result = apt.reposync(mock_connection)

        mock_connection.run.assert_called_once_with(
            "apt-get update", hide=True, warn=True
        )
        assert result is expected

    def test_get_updates(self, mocker, mock_pkg_output):
        """
        Test the get_updates method of the Apt provider.
        """
        apt = Apt()
        updates: list[Update] = apt.get_updates(mock_pkg_output)

        assert len(updates) == 6
        assert updates[0].name == "base-files"
        assert updates[0].current_version == "12.4+deb12u10"
        assert updates[0].new_version == "12.4+deb12u11"
        assert updates[0].source == "Debian:12.11/stable"
        assert not updates[0].security

        # Ensure security updates are correctly identified
        assert updates[5].name == "big-patch"
        assert updates[5].security

    def test_get_updates_no_updates(self, mocker, mock_connection):
        """
        Test the get_updates method of the Apt provider when no updates are available.
        """
        apt = Apt()
        mock_connection.run.return_value.stdout = ""

        updates: list[Update] = apt.get_updates(mock_connection)

        assert updates == []
