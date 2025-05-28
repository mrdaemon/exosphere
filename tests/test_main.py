from pathlib import Path

import pytest
import yaml

from exosphere.config import Configuration
from exosphere.main import load_first_config


class TestMain:
    @pytest.fixture()
    def mock_config(self, mocker):
        """
        Fixture to create a mock configuration object.
        """
        mocker.patch.object(
            Configuration, "from_file", return_value=True, autospec=True
        )
        mock_config = Configuration()
        return mock_config

    @pytest.fixture()
    def mock_config_exception(self, mocker):
        """
        Fixture to create a mock configuration object that raises an exception.
        """
        mocker.patch.object(
            Configuration, "from_file", side_effect=Exception("Test exception")
        )
        mock_config = Configuration()
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
        mocker.patch("pathlib.Path.exists", return_value=True)
        first_path = Path.home() / ".config" / "exosphere" / "config.yaml"

        result = load_first_config(mock_config)

        assert result is True
        mock_config.from_file.assert_called_once_with(
            mock_config, str(first_path), yaml.safe_load, silent=True
        )

    def test_load_first_config_no_file(self, mocker, mock_config):
        """
        Test the load_first_config function when no file is found.
        """
        mocker.patch("pathlib.Path.exists", return_value=False)

        result = load_first_config(mock_config)

        assert result is False
        mock_config.from_file.assert_not_called()

    def test_load_first_config_invalid_file(self, mocker, mock_config_exception):
        """
        Test the load_first_config function when an invalid file is found.
        It should raise a SystemExit exception via sys.exit(1)
        """
        mocker.patch("pathlib.Path.exists", return_value=True)

        with pytest.raises(SystemExit):
            load_first_config(mock_config_exception)
