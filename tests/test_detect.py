import pytest

from exosphere.setup.detect import os_detect, flavor_detect, version_detect
from exosphere.errors import DataRefreshError, UnsupportedOSError


class TestDetection:
    def test_os_detect(self, connection) -> None:
        # Mock the connection to return a specific OS type
        connection.run.return_value.stdout = "Linux\n"
        connection.run.return_value.failed = False

        # Call the function to test
        os_type = os_detect(connection)

        # Assert that the detected OS type is as expected
        assert os_type == "linux"

    def test_os_detect_connection_failure(self, connection):
        # Mock the connection to simulate a failure in OS detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            os_detect(connection)

    @pytest.mark.parametrize(
        "os_name,id,like,expected",
        [
            ("linux", "ubuntu", "debian", "ubuntu"),
            ("linux", "fedora", "rhel", "rhel"),
            ("freebsd", "", "", "freebsd"),
        ],
        ids=["ubuntu", "rhel", "freebsd"],
    )
    def test_flavor_detect(self, connection, os_name, id, like, expected) -> None:
        # Mock the connection to return the id and like id in sequence
        connection.run.side_effect = [
            type(
                "MockResponse", (object,), {"stdout": f'ID="{id}"\n', "failed": False}
            )(),
            type(
                "MockResponse",
                (object,),
                {"stdout": f'ID_LIKE="{like}"\n', "failed": False},
            )(),
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
        connection.run.return_value.failed = False

        # Mock the connection to return the id and like id in sequence
        connection.run.side_effect = [
            type(
                "MockResponse", (object,), {"stdout": f'ID="{id}"\n', "failed": False}
            )(),
            type(
                "MockResponse",
                (object,),
                {"stdout": f'ID_LIKE="{like}"\n', "failed": False},
            )(),
        ]

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(UnsupportedOSError):
            flavor_detect(connection, os_name)

    def test_flavor_detect_connection_failure(self, connection) -> None:
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
        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(UnsupportedOSError):
            version_detect(connection, flavor)

    @pytest.mark.parametrize(
        "flavor",
        ["ubuntu", "debian", "rhel", "freebsd"],
    )
    def test_version_detect_connection_failure(self, connection, flavor) -> None:
        # Mock the connection to simulate a failure in version detection
        connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            version_detect(connection, flavor)
