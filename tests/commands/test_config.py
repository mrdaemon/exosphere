import pytest

from exosphere.commands import config
from exosphere.config import Configuration


class DummyContext:
    """
    Dummy context class to simulate exosphere.context
    """

    def __init__(self, confpath: str | None = "/fake/path/config.yaml"):
        self.confpath: str | None = confpath


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the config command module."""
    patch_console(config)


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

    def test_all_options(self, app_config, capsys):
        """
        Test the 'show' command with no specific option.
        """
        code = config.app(["show"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        for key in Configuration.DEFAULTS["options"]:
            assert key in out

    def test_specific_option(self, app_config, capsys):
        """
        Test the 'show' command with a specific option.
        """
        # We pick the first one from defaults
        option = next(iter(Configuration.DEFAULTS["options"]))

        code = config.app(["show", option], result_action="return_value")

        assert code == 0
        assert str(Configuration.DEFAULTS["options"][option]) in capsys.readouterr().out

    def test_option_not_found(self, app_config, capsys):
        """
        Test the 'show' command with an invalid option.
        """
        code = config.app(["show", "non_existent_option"], result_action="return_value")

        assert code == 1  # Input error: unknown option
        assert "not found in configuration" in capsys.readouterr().err

    def test_full_config(self, app_config, capsys):
        """
        Test the 'show' command with the --full option.
        """
        code = config.app(["show", "--full"], result_action="return_value")

        out = capsys.readouterr().out
        assert code == 0
        assert "hosts" in out
        assert "localhost" in out
        assert "127.0.0.1" in out

    def test_full_config_with_option_warns(self, app_config, capsys):
        """
        Tests that 'show' with option name gives a warning when --full is used.
        """
        code = config.app(
            ["show", "some_option", "--full"], result_action="return_value"
        )

        assert code == 0
        assert "ignoring option name" in capsys.readouterr().err


class TestSourceCommand:
    """Tests for the 'config source' command."""

    def test_shows_config_path(self, mocker, app_config, capsys):
        """
        Test that 'source' command shows the current configuration.
        """
        mocker.patch(
            "exosphere.commands.config.context",
            DummyContext(confpath="/tmp/config.yaml"),
        )

        config.app(["source"], result_action="return_value")

        assert "/tmp/config.yaml" in capsys.readouterr().out

    def test_with_env(self, monkeypatch, app_config, capsys):
        """
        Test that 'source' command shows environment variable overrides.
        """
        monkeypatch.setenv(
            "EXOSPHERE_OPTIONS_" + next(iter(Configuration.DEFAULTS["options"])),
            "testvalue",
        )

        config.app(["source"], result_action="return_value")

        assert "Environment variable overrides" in capsys.readouterr().out

    def test_no_config(self, mocker, app_config, capsys):
        """
        Test that 'source' command shows a message when no configuration is loaded.
        """
        mocker.patch("exosphere.commands.config.context", DummyContext(confpath=None))

        config.app(["source"], result_action="return_value")

        assert "No configuration loaded" in capsys.readouterr().err


class TestPathsCommand:
    """Tests for the 'config paths' command."""

    def test_shows_directories(self, mocker, app_config, capsys):
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
        config.app(["paths"], result_action="return_value")

        out = capsys.readouterr().out
        assert "Application directories" in out
        assert "Config: /tmp/config" in out
        assert "Cache: /tmp/cache" in out
        assert "Logs: /tmp/logs" in out
        assert "State: /tmp/state" in out

    def test_no_config(self, mocker, app_config, capsys):
        """
        Test that 'paths' command shows a message when no configuration is loaded.
        """
        mocker.patch("exosphere.commands.config.context", DummyContext(confpath=None))

        config.app(["paths"], result_action="return_value")

        assert "No configuration file loaded" in capsys.readouterr().err


class TestDiffCommand:
    """Tests for the 'config diff' command."""

    def test_no_difference(self, app_config, capsys):
        """
        Assert that 'diff' command shows no differences when no changes are made.
        """
        config.app(["diff"], result_action="return_value")

        # Should not show any differences if no changes are made
        assert "No differences found" in capsys.readouterr().out

    def test_with_changes(self, app_config_with_changes, capsys):
        """
        Assert that 'diff' command shows changes when configuration is modified.
        """
        config.app(["diff"], result_action="return_value")

        # Should show changed options in green and mention the default value in yellow
        out = capsys.readouterr().out
        assert "'debug': True" in out
        assert "# default: False" in out
        assert "'log_level': 'DEBUG'" in out
        assert "# default: 'INFO'" in out
        assert "'default_timeout': 30" in out

    def test_full_with_changes(self, app_config_with_changes, capsys):
        """
        Assert that full 'diff' command shows defaults
        """
        config.app(["diff", "--full"], result_action="return_value")

        # Should show all options, changed in green, unchanged in dim
        out = capsys.readouterr().out
        assert "'debug': True" in out
        assert "'log_level': 'DEBUG'" in out
        assert "'default_timeout': 30" in out

        # Unchanged options should also appear (dim style, but we check presence)
        for key in Configuration.DEFAULTS["options"]:
            assert repr(key) in out
