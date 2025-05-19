import tomllib

import pytest
import yaml

from exosphere.inventory import Configuration

# FIXME: these tests are garbage, need fixtures, and need functional coverage.


class TestConfiguration:
    @pytest.fixture()
    def config_defaults(self):
        return Configuration.DEFAULTS

    @pytest.fixture()
    def expected_config(self):
        data = {
            "options": {
                "log_level": "DEBUG",
            },
            "hosts": [
                {"name": "host1", "ip": "127.0.0.1"},
                {"name": "host2", "ip": "127.0.0.2"},
            ],
        }

        return data

    @pytest.fixture()
    def toml_config_file(self, tmp_path):
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

        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)
        return config_file

    @pytest.fixture()
    def yaml_config_file(self, tmp_path):
        yaml_content = """
        options:
          log_level: DEBUG
        hosts:
          - name: host1
            ip: 127.0.0.1
          - name: host2
            ip: 127.0.0.2
        """

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        return config_file

    @pytest.fixture()
    def toml_config_file_extra(self, tmp_path):
        toml_content = """
        [options]
        log_level = "DEBUG"
        
        [[hosts]]
        name = "host1"
        ip = "127.0.0.1"

        [[hosts]]
        name = "host2"
        ip = "127.0.0.2"

        [unrecognized_section]
        name = "extra"
        description = "This is an unparsed section"
        """

        config_file = tmp_path / "config_extra.toml"
        config_file.write_text(toml_content)
        return config_file

    @pytest.fixture()
    def yaml_config_file_extra(self, tmp_path):
        yaml_content = """
        options:
          log_level: DEBUG
        hosts:
          - name: host1
            ip: 127.0.0.1
          - name: host2
            ip: 127.0.0.2
        unrecognized_section:
          name: extra
          description: This is an unparsed section
        """

        config_file = tmp_path / "config_extra.yaml"
        config_file.write_text(yaml_content)
        return config_file

    def test_initialization(self, config_defaults):
        config = Configuration()

        assert isinstance(config, Configuration)
        assert config == config_defaults

    def test_from_toml(self, toml_config_file, expected_config):
        config = Configuration()

        assert config.from_toml(toml_config_file) is True

        assert config == expected_config

    def test_from_yaml(self, yaml_config_file, expected_config):
        config = Configuration()

        assert config.from_yaml(yaml_config_file) is True

        assert config == expected_config

    @pytest.mark.parametrize(
        "config_file, loader",
        [
            ("toml_config_file", tomllib.load),
            ("yaml_config_file", yaml.safe_load),
        ],
        ids=["toml", "yaml"],
    )
    def test_from_file(self, request, config_file, loader, expected_config):
        config = Configuration()

        config_file = request.getfixturevalue(config_file)
        assert config.from_file(config_file, loader) is True

        assert config == expected_config

    @pytest.mark.parametrize(
        "loader",
        [
            (tomllib.load),
            (yaml.safe_load),
        ],
        ids=["toml", "yaml"],
    )
    def test_invalid_config(self, tmp_path, loader):
        config = Configuration()
        invalid_file = tmp_path / "invalid_config.cfg"
        invalid_file.write_text("invalid content")

        with pytest.raises(Exception):
            config.from_file(invalid_file, loader)

    @pytest.mark.parametrize(
        "config_file_extra, loader",
        [
            ("toml_config_file_extra", tomllib.load),
            ("yaml_config_file_extra", yaml.safe_load),
        ],
        ids=["toml", "yaml"],
    )
    def test_from_file_extra(self, request, config_file_extra, loader, expected_config):
        config = Configuration()
        config_file = request.getfixturevalue(config_file_extra)
        assert config.from_file(config_file, loader) is True

        assert "unrecognized_section" not in config
        assert config == expected_config
