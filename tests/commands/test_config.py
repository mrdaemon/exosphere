import pytest
from typer.testing import CliRunner

from exosphere.commands import config
from exosphere.config import Configuration

runner = CliRunner()


class DummyContext:
    """
    Dummy context class to simulate exosphere.context
    """

    def __init__(self, confpath: str | None = "/fake/path/config.yaml"):
        self.confpath: str | None = confpath


@pytest.fixture(autouse=True)
def patch_context(mocker):
    """
    Fixture to patch the context with a fake configuration path.
    Any further changes to 'context' should be implemented here.
    """
    dummy_context = mocker.patch("exosphere.commands.config.context", DummyContext())
    return dummy_context


@pytest.fixture
def config_object():
    """
    Fresh configuration object with default values, but also
    an inventory section under the "hosts" key.
    """
    conf = Configuration()

    conf.update_from_mapping(
        {
            "hosts": [
                {
                    "name": "localhost",
                    "ip": "127.0.0.1",
                }
            ]
        }
    )

    return conf


@pytest.fixture
def app_config(mocker, config_object):
    """
    Fixture to patch the app_config with a fresh configuration object.
    """
    mocker.patch("exosphere.commands.config.app_config", config_object)
    return config_object


@pytest.fixture
def app_config_with_changes(mocker):
    """
    Fixture to patch the app_config with modified configuration options.
    This simulates a configuration with some options changed from their defaults.
    """
    modified_config = Configuration()
    modified_config.update_from_mapping(
        {"options": {"debug": True, "log_level": "DEBUG", "default_timeout": 30}}
    )

    mocker.patch("exosphere.commands.config.app_config", modified_config)
    return modified_config


class TestShowCommand:
    """Tests for the 'config show' command."""

    def test_all_options(self, app_config):
        """
        Test the 'show' command with no specific option.
        """
        result = runner.invoke(config.app, ["show"])

        assert result.exit_code == 0

        for key in Configuration.DEFAULTS["options"]:
            assert key in result.output

    def test_specific_option(self, app_config):
        """
        Test the 'show' command with a specific option.
        """
        # We pick the first one from defaults
        option = next(iter(Configuration.DEFAULTS["options"]))

        result = runner.invoke(config.app, ["show", option])

        assert result.exit_code == 0
        assert str(Configuration.DEFAULTS["options"][option]) in result.output

    def test_option_not_found(self, app_config):
        """
        Test the 'show' command with an invalid option.
        """
        result = runner.invoke(config.app, ["show", "non_existent_option"])

        assert result.exit_code != 0  # Expecting a non-zero exit code
        assert "not found in configuration" in result.output

    def test_full_config(self, app_config):
        """
        Test the 'show' command with the --full option.
        """
        result = runner.invoke(config.app, ["show", "--full"])

        assert result.exit_code == 0
        assert "hosts" in result.output
        assert "localhost" in result.output
        assert "127.0.0.1" in result.output

    def test_full_config_with_option_warns(self, app_config):
        """
        Tests that 'show' with option name gives a warning when --full is used.
        """
        result = runner.invoke(config.app, ["show", "some_option", "--full"])

        assert result.exit_code == 0
        assert "ignoring option name" in result.output


class TestSourceCommand:
    """Tests for the 'config source' command."""

    def test_shows_config_path(self, mocker, app_config):
        """
        Test that 'source' command shows the current configuration.
        """
        mocker.patch(
            "exosphere.commands.config.context",
            DummyContext(confpath="/tmp/config.yaml"),
        )

        result = runner.invoke(config.app, ["source"])

        assert result.exit_code == 0
        assert "/tmp/config.yaml" in result.output

    def test_with_env(self, monkeypatch, app_config):
        """
        Test that 'source' command shows environment variable overrides.
        """
        monkeypatch.setenv(
            "EXOSPHERE_OPTIONS_" + next(iter(Configuration.DEFAULTS["options"])),
            "testvalue",
        )

        result = runner.invoke(config.app, ["source"])

        assert result.exit_code == 0
        assert "Environment variable overrides" in result.output

    def test_no_config(self, mocker, app_config):
        """
        Test that 'source' command shows a message when no configuration is loaded.
        """
        mocker.patch("exosphere.commands.config.context", DummyContext(confpath=None))

        result = runner.invoke(config.app, ["source"])

        assert result.exit_code == 0
        assert "No configuration loaded" in result.output


class TestPathsCommand:
    """Tests for the 'config paths' command."""

    def test_shows_directories(self, mocker, app_config):
        """
        Test that 'paths' command shows application directories.
        """
        mocker.patch(
            "exosphere.commands.config.fspaths.get_dirs",
            lambda: {
                "config": "/tmp/config",
                "cache": "/tmp/cache",
                "logs": "/tmp/logs",
                "state": "/tmp/state",
            },
        )
        result = runner.invoke(config.app, ["paths"])

        assert result.exit_code == 0

        assert "Application directories" in result.output
        assert "Config: /tmp/config" in result.output
        assert "Cache: /tmp/cache" in result.output
        assert "Logs: /tmp/logs" in result.output
        assert "State: /tmp/state" in result.output

    def test_no_config(self, mocker, app_config):
        """
        Test that 'paths' command shows a message when no configuration is loaded.
        """
        mocker.patch("exosphere.commands.config.context", DummyContext(confpath=None))

        result = runner.invoke(config.app, ["paths"])

        assert result.exit_code == 0
        assert "No configuration file loaded" in result.output


class TestDiffCommand:
    """Tests for the 'config diff' command."""

    def test_no_difference(self, app_config):
        """
        Assert that 'diff' command shows no differences when no changes are made.
        """
        result = runner.invoke(config.app, ["diff"])

        assert result.exit_code == 0

        # Should not show any differences if no changes are made
        assert "No differences found" in result.output

    def test_with_changes(self, app_config_with_changes):
        """
        Assert that 'diff' command shows changes when configuration is modified.
        """
        result = runner.invoke(config.app, ["diff"])

        assert result.exit_code == 0

        # Should show changed options in green and mention the default value in yellow
        assert "'debug': True" in result.output
        assert "# default: False" in result.output
        assert "'log_level': 'DEBUG'" in result.output
        assert "# default: 'INFO'" in result.output
        assert "'default_timeout': 30" in result.output

    def test_full_with_changes(self, app_config_with_changes):
        """
        Assert that full 'diff' command shows defaults
        """
        result = runner.invoke(config.app, ["diff", "--full"])

        assert result.exit_code == 0

        # Should show all options, changed in green, unchanged in dim
        assert "'debug': True" in result.output
        assert "'log_level': 'DEBUG'" in result.output
        assert "'default_timeout': 30" in result.output

        # Unchanged options should also appear (dim style, but we check presence)
        for key in Configuration.DEFAULTS["options"]:
            assert repr(key) in result.output
