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

    def test_main(self, mocker):
        """
        Test the main function of the Exosphere application.
        """
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

    def test_load_first_config(self, mocker, mock_config):
        """
        Test the load_first_config function.
        """
        from exosphere.main import load_first_config

        mocker.patch("pathlib.Path.exists", return_value=True)
        first_path = Path.home() / ".config" / "exosphere" / "config.yaml"

        result = load_first_config(mock_config)

        assert result is True
        mock_config.from_file.assert_called_once_with(
            str(first_path), yaml.safe_load, silent=True
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
        config_path = Path.home() / ".my_config.yaml"

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
