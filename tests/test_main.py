from pathlib import Path

import pytest
import yaml

from exosphere.inventory import Configuration
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
