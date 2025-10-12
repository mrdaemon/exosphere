"""
Tests for the version command module.
"""

import json
from urllib.error import URLError

import pytest
from typer.testing import CliRunner

from exosphere.commands import version
from exosphere.config import Configuration

runner = CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture
def mock_version(mocker):
    """Mock the __version__ variable."""
    return mocker.patch("exosphere.commands.version.__version__", "1.5.0")


@pytest.fixture
def mock_urlopen(mocker):
    """Mock urllib.request.urlopen for PyPI API calls."""
    return mocker.patch("exosphere.commands.version.urllib.request.urlopen")


@pytest.fixture
def app_config(mocker):
    """
    Fixture to patch the app_config with a fresh configuration object.
    """
    config_object = Configuration()
    # Enable PyPI checks by default in tests
    # This should be the stock defaults but we explicitly set it here
    # for consistency of results, should this ever change.
    config_object.update_from_mapping({"options": {"update_checks": True}})
    mocker.patch("exosphere.commands.version.app_config", config_object)
    return config_object


@pytest.fixture
def app_config_pypi_disabled(mocker):
    """
    Fixture to patch the app_config with PyPI checks disabled.
    """
    config_object = Configuration()
    config_object.update_from_mapping({"options": {"update_checks": False}})
    mocker.patch("exosphere.commands.version.app_config", config_object)
    return config_object


@pytest.fixture
def create_pypi_response(mocker):
    """
    Factory fixture that creates mock PyPI API responses

    Returned function takes a version string and returns a configured mock.
    """

    def _create_response(version_string: str):
        response_data = {"info": {"version": version_string}}
        mock_response = mocker.Mock()
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=False)
        mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
        return mock_response

    return _create_response


class TestVersionDefault:
    """Tests for the default version command (no subcommand)."""

    def test_version_default_displays_version(self):
        """Test that the default version command displays the version."""
        result = runner.invoke(version.app, [])

        assert result.exit_code == 0
        assert "Exosphere version" in result.output

    def test_version_help(self):
        """
        Test that version --help shows the help message.

        Additionally, default command should not fire off
        """
        result = runner.invoke(version.app, ["--help"])

        assert result.exit_code == 0
        assert "Version and Update Check Commands" in result.output
        assert "check" in result.output


class TestVersionDetails:
    """Tests for the 'version details' command."""

    def test_details_command_displays_environment_table(self):
        """
        Test that 'details' command displays environment information table.

        Verifies that the command exits successfully and displays the expected
        categories in the output.
        """
        result = runner.invoke(version.app, ["details"])

        assert result.exit_code == 0
        assert "Python" in result.output
        assert "System" in result.output
        assert "Exosphere" in result.output


class TestVersionCheck:
    """Tests for the 'version check' command."""

    def test_check_update_available(
        self, mock_urlopen, app_config, mocker, create_pypi_response
    ):
        """Test check when an update is available."""
        # Mock current version as older version
        mocker.patch("exosphere.commands.version.__version__", "1.4.0")

        # Mock PyPI response with newer version
        mock_urlopen.return_value = create_pypi_response("1.5.0")

        result = runner.invoke(version.app, ["check"])

        assert "new version is available" in result.output
        assert "1.5.0" in result.output
        assert result.exit_code == 3

    def test_check_latest_version(
        self, mock_urlopen, mock_version, app_config, create_pypi_response
    ):
        """Test check when using the latest version."""
        # Mock PyPI response with same version
        mock_urlopen.return_value = create_pypi_response("1.5.0")

        result = runner.invoke(version.app, ["check"])

        assert result.exit_code == 0
        assert "latest version" in result.output

    def test_check_development_version(
        self, mock_urlopen, app_config, mocker, create_pypi_response
    ):
        """Test check when using a development version."""
        # Mock current version as development version (newer than stable)
        mocker.patch("exosphere.commands.version.__version__", "1.6.0.dev0")

        # Mock PyPI response with older stable version
        mock_urlopen.return_value = create_pypi_response("1.5.0")

        result = runner.invoke(version.app, ["check"])

        assert result.exit_code == 0
        assert "development version" in result.output

    @pytest.mark.parametrize("verbose_flag", ["--verbose", "-v"], ids=["long", "short"])
    def test_check_verbose(
        self, mock_urlopen, mock_version, app_config, verbose_flag, create_pypi_response
    ):
        """Test check with verbose flag."""
        # Mock PyPI response
        mock_urlopen.return_value = create_pypi_response("1.5.0")

        result = runner.invoke(version.app, ["check", verbose_flag])

        assert result.exit_code == 0
        # Verbose should print current version and checking message
        assert "Current version" in result.output or "Checking PyPI" in result.output

    def test_check_network_error(self, mock_urlopen, mock_version, app_config):
        """Test check with network error."""
        # Mock urlopen to raise URLError
        mock_urlopen.side_effect = URLError("Network unreachable")

        result = runner.invoke(version.app, ["check"])

        assert result.exit_code == 1
        assert "Error" in result.output or "Failed" in result.output

    def test_check_malformed_pypi_response(
        self, mock_urlopen, mock_version, app_config, mocker
    ):
        """Test check with malformed PyPI response (missing version key)."""
        # Mock PyPI response with missing 'version' key
        response_data = {"info": {}}  # Missing 'version' key
        mock_response = mocker.Mock()
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=False)
        mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_urlopen.return_value = mock_response

        result = runner.invoke(version.app, ["check"])

        assert result.exit_code == 1
        assert "Error" in result.output or "Unexpected" in result.output

    def test_check_invalid_json_response(
        self, mock_urlopen, mock_version, app_config, mocker
    ):
        """Test check with invalid JSON response from PyPI."""
        # Mock PyPI response with invalid JSON
        mock_response = mocker.Mock()
        mock_response.__enter__ = mocker.Mock(return_value=mock_response)
        mock_response.__exit__ = mocker.Mock(return_value=False)
        mock_response.read.return_value = b"Not valid JSON"
        mock_urlopen.return_value = mock_response

        result = runner.invoke(version.app, ["check"])

        assert result.exit_code == 1
        assert "Error" in result.output or "Failed" in result.output

    def test_check_pypi_disabled(self, mock_urlopen, app_config_pypi_disabled):
        """Test check when PyPI checks are disabled via configuration."""
        result = runner.invoke(version.app, ["check"])

        mock_urlopen.assert_not_called()
        assert "disabled" in result.output.lower()
        assert result.exit_code == 1

    def test_check_timeout(
        self, mock_urlopen, mock_version, app_config, create_pypi_response
    ):
        """Test that urlopen is called with correct timeout."""
        # Mock PyPI response
        mock_urlopen.return_value = create_pypi_response("1.5.0")

        runner.invoke(version.app, ["check"])

        # Verify urlopen was called with timeout parameter
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        # Check that timeout was passed (either as kwarg or in args)
        assert call_args.kwargs.get("timeout") == 5 or (
            len(call_args.args) > 1 and call_args.args[1] == 5
        )
