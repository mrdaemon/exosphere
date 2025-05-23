from unittest.mock import MagicMock

import pytest

from exosphere.data import HostInfo
from exosphere.errors import DataRefreshError, OfflineHostError, UnsupportedOSError
from exosphere.setup.detect import (
    flavor_detect,
    os_detect,
    package_manager_detect,
    platform_detect,
    version_detect,
)


def _run_return(failed: bool, stdout: str = "") -> MagicMock:
    """
    Helper function that returns a MagicMock intended
    to mock the return value of a connection.run() call.

    It is not a fixture since it needs to be invoked as a
    side effect of the connection.run() call in parametrized
    tests.
    """
    mock_return = MagicMock()
    mock_return.stdout = stdout
    mock_return.failed = failed
    return mock_return


class TestDetection:
    def test_os_detect(self, connection) -> None:
        """
        Basic functional test for os_detect.
        """
        # Mock the connection to return a specific OS type
        connection.run.return_value.stdout = "Linux\n"
        connection.run.return_value.failed = False

        # Call the function to test
        os_type = os_detect(connection)

        # Assert that the detected OS type is as expected
        assert os_type == "linux"

    def test_os_detect_connection_failure(self, connection):
        """
        Test for os_detect when the connection or implementation fails.
        """
        # Mock the connection to simulate a failure in OS detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            os_detect(connection)

    @pytest.mark.parametrize(
        "os_name,id,like,expected",
        [
            ("linux", "ubuntu", "debian", "ubuntu"),
            ("linux", "fedora", "rhel fedora", "rhel"),
            ("linux", "almalinux", "rhel centos fedora", "rhel"),
            ("linux", "rockylinux", "rhel centos fedora", "rhel"),
            ("freebsd", "", "", "freebsd"),
        ],
        ids=["ubuntu", "fedora", "almalinux", "centos", "freebsd"],
    )
    def test_flavor_detect(self, connection, os_name, id, like, expected) -> None:
        """
        Basic functional test for detection of OS flavors.
        """
        # Mock the connection to return the id and like id in sequence
        connection.run.side_effect = [
            _run_return(False, f'ID="{id}"\n'),
            _run_return(False, f'ID_LIKE="{like}"\n'),
        ]

        # Call the function to test
        flavor = flavor_detect(connection, os_name)

        # Assert that the detected flavor is as expected
        assert flavor == expected

    @pytest.mark.parametrize(
        "os_name,id,like",
        [
            ("linux", "arch", "arch"),
            ("linux", "gentoo", "gentoo"),
            ("openbsd", "", "openbsd"),
        ],
        ids=["arch", "gentoo", "openbsd"],
    )
    def test_flavor_detect_failure(self, connection, os_name, id, like) -> None:
        """
        Test for flavor detection when the OS is unsupported or
        the connection and/or implementation fails.
        """
        connection.run.return_value.failed = False

        # Mock the connection to return the id and like id in sequence
        connection.run.side_effect = [
            _run_return(False, f'ID="{id}"\n'),
            _run_return(False, f'ID_LIKE="{like}"\n'),
        ]

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(UnsupportedOSError):
            flavor_detect(connection, os_name)

    def test_flavor_detect_no_id_like(self, connection) -> None:
        """
        Test for flavor detection failure when no ID_LIKE is present
        in the os-release file.
        """
        # Mock the connection to return an empty ID and ID_LIKE
        connection.run.side_effect = [
            _run_return(False, 'ID="MagixOS"\n'),
            _run_return(True, ""),  # no ID_LIKE
        ]

        # Call the function and expect it to raise an UnsupportedOSError
        with pytest.raises(UnsupportedOSError):
            flavor_detect(connection, "linux")

    def test_flavor_detect_connection_failure(self, connection) -> None:
        """
        Test for flavor detection when the connection or implementation fails.
        """
        # Mock the connection to simulate a failure in flavor detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            flavor_detect(connection, "linux")

    @pytest.mark.parametrize(
        "flavor,stdout,expected",
        [
            ("ubuntu", "20.04\n", "20.04"),
            ("debian", "12\n", "12"),
            ("rhel", 'VERSION_ID="8.3"\n', "8.3"),
            ("freebsd", "13.0-RELEASE-p4\n", "13.0-RELEASE-p4"),
        ],
        ids=["ubuntu", "debian", "rhel", "freebsd"],
    )
    def test_version_detect(self, connection, flavor, stdout, expected) -> None:
        """
        Basic functional test for version detection.
        """
        # Mock the connection to return a specific version string
        connection.run.return_value.stdout = stdout
        connection.run.return_value.failed = False

        # Call the function to test
        version = version_detect(connection, flavor)

        # Assert that the detected version is as expected
        assert version == expected

    @pytest.mark.parametrize(
        "flavor",
        ["arch", "gentoo", "openbsd"],  # Unsupported flavors
    )
    def test_version_detect_failure(self, connection, flavor) -> None:
        """
        Test for version detection failure when the OS is unsupported
        """
        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(UnsupportedOSError):
            version_detect(connection, flavor)

    @pytest.mark.parametrize(
        "flavor",
        ["ubuntu", "debian", "rhel", "freebsd"],
    )
    def test_version_detect_connection_failure(self, connection, flavor) -> None:
        """
        Test for version detection when the connection or implementation fails.
        """
        # Mock the connection to simulate a failure in version detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            version_detect(connection, flavor)

    @pytest.mark.parametrize(
        "flavor,fallback,expected",
        [
            ("ubuntu", False, "apt"),
            ("debian", False, "apt"),
            ("rhel", True, "yum"),
            ("rhel", False, "dnf"),
            ("freebsd", False, "pkg"),
        ],
        ids=["ubuntu", "debian", "rhel_fallback", "rhel_no_fallback", "freebsd"],
    )
    def test_package_manager_detect(
        self, connection, flavor, fallback, expected
    ) -> None:
        """
        Basic functional test for package manager detection.
        """
        connection.run.return_value.failed = False

        if fallback:
            connection.run.side_effect = [
                _run_return(True),
                _run_return(False),
            ]

        # Call the function to test
        package_manager = package_manager_detect(connection, flavor)

        # Assert that the detected package manager is as expected
        assert package_manager == expected

    @pytest.mark.parametrize(
        "flavor",
        ["unsupported_flavor", "rhel"],
        ids=["unsupported_flavor", "rhel_with_no_fallback"],
    )
    def test_package_manager_detect_failure(self, connection, flavor) -> None:
        """
        Test for package manager detection failure when the OS is unsupported
        or the connection and/or implementation fails.
        """
        # Mock the connection to simulate a failure in package manager detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(UnsupportedOSError):
            package_manager_detect(connection, flavor)

    def test_platform_detect(self, connection) -> None:
        """
        Very basic end to end test for platform detection
        """
        # mock the connection to return a series of values in a mock
        # object, as the stdout attribute of the mock object
        connection.run.side_effect = [
            _run_return(False, "Linux\n"),
            _run_return(False, 'ID="debian"\n'),
            _run_return(True, ""),  # no ID_LIKE
            _run_return(False, "12\n"),
            _run_return(False, "apt\n"),
        ]

        expected = HostInfo(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
        )

        # Call the function to test
        platform_info = platform_detect(connection)

        assert platform_info == expected

    def test_platform_detect_timeout(self, connection) -> None:
        """
        Test for platform detection handling of Timeout Errors
        """
        # Mock the connection to simulate a timeout
        connection.run.side_effect = TimeoutError("Connection timed out")

        # Call the function and expect it to raise an OfflineHostError
        with pytest.raises(OfflineHostError):
            platform_detect(connection)
