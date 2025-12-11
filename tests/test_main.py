from pathlib import Path

import pytest
import yaml


class TestMain:
    @pytest.fixture()
    def mock_config(self, mocker):
        """
        Fixture to create a mock configuration object.
        """
        from exosphere.config import Configuration

        mock_config = mocker.create_autospec(Configuration, instance=True)
        mock_config.from_file.return_value = True
        mock_config.from_env.return_value = True

        return mock_config

    @pytest.fixture()
    def mock_config_exception(self, mocker):
        """
        Fixture to create a mock configuration object that raises an exception.
        """
        from exosphere.config import Configuration

        mock_config = mocker.create_autospec(Configuration, instance=True)
        mock_config.from_file.side_effect = Exception("Test exception")
        mock_config.from_env.return_value = True

        return mock_config

    @pytest.fixture()
    def mock_setup_logging_exception(self, mocker):
        """
        Fixture to create a mock setup_logging function that raises an exception.
        """
        return mocker.patch(
            "exosphere.main.setup_logging",
            side_effect=Exception("Logging setup failed"),
        )

    @pytest.fixture(autouse=True, scope="function")
    def patch_config_dir(self, monkeypatch):
        """
        Fixture to patch the CONFIG_DIR to a specific path for testing.
        This ensures that tests do not depend on platform-specific paths.

        """
        monkeypatch.setattr(
            "exosphere.fspaths.CONFIG_DIR", Path.home() / ".config" / "exosphere"
        )

    @pytest.fixture()
    def mock_reaper(self, mocker):
        """
        Fixture to create a mock ConnectionReaper.
        """
        mock = mocker.MagicMock()
        mock.is_running = True
        return mock

    @pytest.fixture()
    def mock_inventory(self, mocker):
        """
        Fixture to create a mock Inventory.
        """
        return mocker.MagicMock()

    def test_main(self, mocker, caplog):
        """
        Test the main function of the Exosphere application.
        """
        caplog.set_level("INFO", logger="exosphere.main")

        mock_load_first_config = mocker.patch(
            "exosphere.main.load_first_config", return_value=True
        )
        mock_setup_logging = mocker.patch("exosphere.main.setup_logging")

        mock_cli_app = mocker.patch("exosphere.cli.app")

        from exosphere.main import main

        main()

        mock_load_first_config.assert_called_once()
        mock_setup_logging.assert_called_once()
        mock_cli_app.assert_called_once()

        assert "Configuration loaded from:" in caplog.text

    def test_main_ensure_config_paths_are_created(self, mocker):
        """
        Test that the configuration paths are created if they do not exist.
        """

        mocker.patch("exosphere.main.setup_logging")
        mocker.patch("exosphere.cli.app")
        mocker.patch("exosphere.main.load_first_config", return_value=True)

        mock_ensuredirs = mocker.patch("exosphere.main.fspaths.ensure_dirs")

        from exosphere.main import main

        main()

        assert mock_ensuredirs.call_count == 1

    def test_main_ensure_config_paths_aborts_on_error(self, mocker, caplog):
        """
        Test that the main function aborts if ensure_dirs raises an exception.
        """

        mocker.patch("exosphere.main.setup_logging")
        mocker.patch("exosphere.cli.app")
        mocker.patch("exosphere.main.load_first_config", return_value=True)

        mock_ensuredirs = mocker.patch(
            "exosphere.main.fspaths.ensure_dirs", side_effect=Exception("Test error")
        )

        from exosphere.main import main

        with pytest.raises(SystemExit):
            main()

        mock_ensuredirs.assert_called_once()
        assert "Failed to create required directories" in caplog.text

    def test_main_no_config(self, mocker, caplog):
        """
        Test the main function when no configuration is loaded.
        It should log a warning and exit.
        """

        caplog.set_level("WARNING", logger="exosphere.main")

        mocker.patch("exosphere.main.load_first_config", return_value=False)
        mocker.patch("exosphere.main.setup_logging")
        mocker.patch("exosphere.cli.app")

        from exosphere.main import main

        main()

        assert "No configuration file found. Using defaults" in caplog.text

    def test_main_debug_mode_enabled(self, mocker, caplog):
        """
        Test the main function when debug mode is enabled.
        It should log debug messages.
        """

        caplog.set_level("WARNING", logger="exosphere.main")

        mocker.patch("exosphere.main.load_first_config", return_value=True)
        mocker.patch("exosphere.cli.app")

        mock_setup_logging = mocker.patch("exosphere.main.setup_logging")

        # Make a new configuration with debug options
        from exosphere import Configuration

        config = Configuration()

        debug_config = {
            "options": {
                "debug": True,
                "log_level": "DEBUG",
            }
        }

        config.update_from_mapping(debug_config)

        mocker.patch("exosphere.main.app_config", config)

        from exosphere.main import main

        main()

        mock_setup_logging.assert_called_once_with("DEBUG")  # No file!
        assert "Debug mode enabled! Logs may flood console!" in caplog.text

    def test_main_inventory_exception(self, mocker, mock_config):
        """
        Test main exits if Inventory raises an exception.
        """

        mocker.patch("exosphere.main.load_first_config", return_value=True)
        mocker.patch("exosphere.main.setup_logging")
        mocker.patch("exosphere.main.cli.app")

        mocker.patch(
            "exosphere.main.Inventory", side_effect=Exception("Inventory error")
        )

        from exosphere.main import main

        with pytest.raises(SystemExit):
            main()

    def test_load_first_config(self, mocker, mock_config):
        """
        Test the load_first_config function.
        """

        from exosphere.main import load_first_config

        mocker.patch("pathlib.Path.exists", return_value=True)
        expected_path = Path.home() / ".config" / "exosphere" / "config.yaml"

        result = load_first_config(mock_config)

        assert result is True
        mock_config.from_file.assert_called_once_with(
            str(expected_path), yaml.safe_load, silent=True
        )

    def test_load_first_config_no_file(self, mocker, mock_config):
        """
        Test the load_first_config function when no file is found.
        """
        mocker.patch("pathlib.Path.exists", return_value=False)

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is False
        mock_config.from_file.assert_not_called()

    def test_load_first_config_env_var(self, mocker, monkeypatch, mock_config):
        """
        Test the load_first_config function when an environment variable is set.
        It should use the file specified in the environment variable.
        """
        config_path = Path.home() / "configs" / "my_config.yaml"

        mocker.patch("pathlib.Path.exists", return_value=True)

        monkeypatch.setenv("EXOSPHERE_CONFIG_FILE", str(config_path))

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is True
        mock_config.from_file.assert_called_once_with(
            str(config_path), yaml.safe_load, silent=True
        )

    def test_load_first_config_env_var_not_found(
        self, mocker, monkeypatch, mock_config
    ):
        """
        Test the load_first_config function when an environment variable is set
        but the file does not exist.
        It should fail, not fall through to default paths, and return False.
        """
        config_path = Path.home() / ".my_config.yaml"

        mocker.patch("pathlib.Path.exists", return_value=False)

        monkeypatch.setenv("EXOSPHERE_CONFIG_FILE", str(config_path))

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is False
        mock_config.from_file.assert_not_called()

    def test_load_first_config_env_path(self, mocker, monkeypatch, mock_config):
        """
        Test the load_first_config function when an environment variable is set
        for a config path. It should use the file specified in the environment variable.
        """
        config_path = Path.home()

        mocker.patch("pathlib.Path.exists", return_value=True)

        monkeypatch.setenv("EXOSPHERE_CONFIG_PATH", str(config_path))

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is True
        mock_config.from_file.assert_called_once_with(
            str(config_path / "config.yaml"), yaml.safe_load, silent=True
        )

    def test_load_first_config_invalid_file(self, mocker, mock_config_exception):
        """
        Test the load_first_config function when an invalid file is found.
        It should raise a SystemExit exception via sys.exit(1)
        """
        mocker.patch("pathlib.Path.exists", return_value=True)

        from exosphere.main import load_first_config

        with pytest.raises(SystemExit):
            load_first_config(mock_config_exception)

    def test_load_first_config_does_not_load(self, mocker, mock_config, caplog):
        """
        Test the load_first_config function when the file exists but does not load.
        It should log a warning and return False.
        """
        mocker.patch("pathlib.Path.exists", return_value=True)
        mock_config.from_file.return_value = False

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is False
        mock_config.from_file.assert_called()
        assert "Failed to load config file" in caplog.text

    def test_load_first_config_no_loaders(self, mocker, mock_config):
        """
        Test the load_first_config function when no loaders are available.
        It should log an error and return False.
        """
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("exosphere.main.LOADERS", {})

        from exosphere.main import load_first_config

        result = load_first_config(mock_config)

        assert result is False
        mock_config.from_file.assert_not_called()

    def test_setup_logging_stream_handler(self, mocker):
        """
        Test setup_logging with no log_file (should use StreamHandler).
        """

        basic_config = mocker.patch("logging.basicConfig")
        get_logger = mocker.patch("logging.getLogger")

        from exosphere.main import setup_logging

        setup_logging("INFO")

        basic_config.assert_called()
        get_logger.assert_any_call("exosphere")
        get_logger.assert_any_call("exosphere.main")

    def test_setup_logging_file_handler(self, mocker, tmp_path):
        """
        Test setup_logging with a log_file (should use FileHandler).
        """
        basic_config = mocker.patch("logging.basicConfig")
        get_logger = mocker.patch("logging.getLogger")
        log_file = tmp_path / "test.log"

        from exosphere.main import setup_logging

        setup_logging("DEBUG", str(log_file))

        basic_config.assert_called()
        get_logger.assert_any_call("exosphere")
        get_logger.assert_any_call("exosphere.main")

    def test_setup_logging_invalid_log_level(self):
        """
        Test setup_logging with an invalid log level.
        It should raise a ValueError.
        """
        from exosphere.main import setup_logging

        with pytest.raises(ValueError):
            setup_logging("INVALID_LEVEL")

    def test_setup_logging_file_handler_exception(self, mocker, tmp_path):
        """
        Test setup_logging when FileHandler creation fails.
        It should raise an exception.
        """
        # Create a path that will cause FileHandler to fail (invalid directory)
        invalid_log_file = tmp_path / "nonexistent_dir" / "test.log"

        from exosphere.main import setup_logging

        # FileHandler should raise an exception for invalid path
        with pytest.raises(Exception):
            setup_logging("INFO", str(invalid_log_file))

    def test_setup_logging_lowercase_log_level(self, mocker):
        """
        Test setup_logging with a lowercase log level.
        It should normalize to uppercase.
        """
        mocker.patch("logging.basicConfig")
        get_logger = mocker.patch("logging.getLogger")

        from exosphere.main import setup_logging

        try:
            setup_logging("debug")
        except ValueError:
            pytest.fail("setup_logging raised ValueError unexpectedly!")

        # Check if the log level was set to DEBUG
        get_logger.assert_any_call("exosphere")
        get_logger.assert_any_call("exosphere.main")
        get_logger().setLevel.assert_called_with("DEBUG")

    def test_main_logging_setup_exception(
        self, mocker, mock_setup_logging_exception, capsys
    ):
        """
        Test that main function handles setup_logging exceptions gracefully.
        """
        # Patch out most of everything
        mocker.patch("exosphere.main.load_first_config", return_value=True)
        mocker.patch("exosphere.cli.app")
        mocker.patch("exosphere.main.fspaths.ensure_dirs")
        mocker.patch("exosphere.main.Inventory")

        from exosphere.main import main

        # Should raise exception in setup_logging
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Check that we exit with error
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert (
            "FATAL: Startup Error setting up logging: Logging setup failed"
            in captured.err
        )

    def test_main_starts_reaper_thread(self, mocker):
        """
        Test that the connection reaper is started in main.
        """

        mock_reaper_start = mocker.patch("exosphere.main.ConnectionReaper.start")
        mocker.patch("exosphere.main.load_first_config", return_value=True)
        mocker.patch("exosphere.main.setup_logging")
        mocker.patch("exosphere.cli.app")
        mocker.patch("exosphere.main.Inventory")

        from exosphere.main import main

        main()

        mock_reaper_start.assert_called_once()

    @pytest.mark.parametrize(
        "reaper_state,inventory_present,expected_reaper_stop,expected_inventory_close",
        [
            (True, True, True, True),
            (False, True, False, True),
            (None, True, False, True),
            (True, False, True, False),
        ], ids=[
            "reaper_running_inventory_present",
            "reaper_stopped_inventory_present",
            "no_reaper_inventory_present",
            "reaper_running_no_inventory",
        ]
    )
    def test_cleanup_connections(
        self,
        mock_reaper,
        mock_inventory,
        reaper_state,
        inventory_present,
        expected_reaper_stop,
        expected_inventory_close,
    ):
        """
        Test cleanup_connections with various reaper and inventory states.
        This is the atexit handler that runs on program exit.
        """
        from exosphere import context
        from exosphere.main import cleanup_connections

        # Setup context based on parameters
        if reaper_state is None:
            context.reaper = None
        else:
            mock_reaper.is_running = reaper_state
            context.reaper = mock_reaper

        context.inventory = mock_inventory if inventory_present else None

        cleanup_connections()

        if expected_reaper_stop:
            mock_reaper.stop.assert_called_once()
        else:
            mock_reaper.stop.assert_not_called()

        if expected_inventory_close:
            mock_inventory.close_all.assert_called_once_with(clear=True)
        else:
            mock_inventory.close_all.assert_not_called()

