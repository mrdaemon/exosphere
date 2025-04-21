import pytest

from exosphere.setup.detect import os_detect, flavor_detect
from exosphere.errors import DataRefreshError, UnsupportedOSError


class DetectionTests:
    @staticmethod
    def test_os_detect(mock_connection):
        # Mock the connection to return a specific OS type
        mock_connection.run.return_value.stdout = "Linux\n"
        mock_connection.run.return_value.failed = False

        # Call the function to test
        os_type = os_detect(mock_connection)

        # Assert that the detected OS type is as expected
        assert os_type == "linux"

    def test_os_detect_failure(self, mock_connection):
        # Mock the connection to simulate a failure in OS detection
        mock_connection.run.return_value.failed = True

        # Call the function and expect it to raise a DataRefreshError
        with pytest.raises(DataRefreshError):
            os_detect(mock_connection)

    @pytest.mark.parametrize(
        "os,id,like,expected",
        [
            ("linux", "ubuntu", "debian", "ubuntu"),
            (
                "linux",
                "debian",
            )("linux", "fedora", "rhel", "fedora"),
            ("linux", "arch", "", "arch"),
            ("freebsd", "", "", "freebsd"),
        ],
    )
    def test_flavor_detect(self, mock_connection, os, id, like, expected):
        # Mock the connection to return the id and like id in sequence
        mock_connection.run.side_effect = [
            mock_connection.run.return_value(f'ID="{id}"\n'),
            mock_connection.run.return_value(f'ID_LIKE="{like}"\n'),
        ]

        mock_connection.run.return_value.failed = False

        # Call the function to test
        flavor = flavor_detect(mock_connection, "linux")

        # Assert that the detected flavor is as expected
        assert flavor == "ubuntu"
