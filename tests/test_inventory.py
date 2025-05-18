import tomllib

import pytest

from exosphere.inventory import Configuration


class TestConfiguration:
    def test_initialization(self):
        config = Configuration()
        assert isinstance(config, Configuration)
        # FIXME: This test is kind of garbage and I need a Defaults fixture
        assert config["options"]["log_level"] == "INFO"
        assert config["hosts"] == []

    def test_from_toml(self, tmp_path):
        config = Configuration()
        toml_content = """
        [options]
        log_level = "DEBUG"
        
        [[hosts]]
        name = "host1"
        ip = "127.0.0.1"

        [[hosts]]
        name = "host2"
        ip = "127.0.0.2"
        """
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(toml_content)

        assert config.from_toml(toml_file) is True
        assert config["options"]["log_level"] == "DEBUG"
        assert len(config["hosts"]) == 2
        assert config["hosts"][0]["name"] == "host1"
        assert config["hosts"][1]["name"] == "host2"
        assert config["hosts"][0]["ip"] == "127.0.0.1"
        assert config["hosts"][1]["ip"] == "127.0.0.2"

    def test_from_file_invalid(self, tmp_path):
        config = Configuration()
        invalid_file = tmp_path / "invalid_config.toml"
        invalid_file.write_text("invalid content")

        with pytest.raises(Exception):
            config.from_file(invalid_file, tomllib.load)
