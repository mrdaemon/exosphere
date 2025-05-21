import errno
import tomllib

import pytest
import yaml

from exosphere.inventory import Configuration


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
                {"name": "host2", "ip": "127.0.0.2", "port": 22},
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
        port = 22
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
            port: 22
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
        port = 22

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
            port: 22
        unrecognized_section:
          name: extra
          description: This is an unparsed section
        """

        config_file = tmp_path / "config_extra.yaml"
        config_file.write_text(yaml_content)
        return config_file

    def test_initialization(self, config_defaults):
        """
        Ensure that the Configuration object initializes with
        the default values.
        """
        config = Configuration()

        assert isinstance(config, Configuration)
        assert config == config_defaults

    def test_from_toml(self, toml_config_file, expected_config):
        """
        Ensure that the Configuration object can be populated
        from a toml file.
        """
        config = Configuration()

        assert config.from_toml(toml_config_file) is True

        # We don't directly compare the dicts with == because
        # one can be a subset of the other, and that is ok
        # since that's how default values work.
        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

    def test_from_yaml(self, yaml_config_file, expected_config):
        config = Configuration()

        assert config.from_yaml(yaml_config_file) is True

        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

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

        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

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

        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

        assert "unrecognized_section" not in config

    @pytest.mark.parametrize(
        "exception_type, silent_mode",
        [
            (OSError(errno.ENOENT, "File not found"), False),
            (OSError(errno.EISDIR, "is a Directory"), False),
            (OSError(errno.EAGAIN, "Not Available"), True),
        ],
        ids=["file_not_found", "is_directory", "io_error"],
    )
    def test_from_file_ioerror(self, mocker, exception_type, silent_mode):
        """
        Ensure that the Configuration object raises an IOError
        when opening generates an IOError and silent is False,
        or when silent is True and the IOError is not one of the supported
        cases.
        """
        config = Configuration()
        mocker.patch("exosphere.inventory.open", side_effect=exception_type)

        with pytest.raises(IOError):
            config.from_file("non_existent_file.toml", tomllib.load, silent=silent_mode)

    @pytest.mark.parametrize(
        "error_code, error_name",
        [
            (errno.ENOENT, "File not found"),
            (errno.EISDIR, "Is a directory"),
        ],
        ids=["file_not_found", "is_directory"],
    )
    def test_from_file_silent(self, mocker, error_code, error_name):
        """
        Ensure that the Configuration object does not raise an
        IOError when the file cannot be opened and silent is True.
        """
        config = Configuration()
        mocker.patch(
            "exosphere.inventory.open", side_effect=OSError(error_code, error_name)
        )

        try:
            result = config.from_file(
                "non_existent_file.toml", tomllib.load, silent=True
            )
        except IOError:
            pytest.fail("IOError should not have been raised with silent=True")

        assert result is False

    def test_update_from_mapping(self, caplog):
        """
        Ensure that the Configuration object can be updated
        from a mapping and discards invalid keys.
        """
        config = Configuration()

        new_mapping = {
            "options": {"log_level": "INFO"},
            "hosts": [
                {"name": "host3", "ip": "172.16.64.3"},
                {"name": "host4", "ip": "172.16.64.4", "port": 22},
            ],
            "invalid_key": [{"name": "invalid"}],
        }
        result = config.update_from_mapping(new_mapping)

        assert result is True

        assert config["options"]["log_level"] == "INFO"
        assert len(config["hosts"]) == 2
        assert config["hosts"][0]["name"] == "host3"
        assert config["hosts"][1]["name"] == "host4"
        assert config["hosts"][0]["ip"] == "172.16.64.3"
        assert config["hosts"][1]["ip"] == "172.16.64.4"
        assert config["hosts"][1]["port"] == 22

        assert "invalid_key" not in config
        assert "is not a valid root key" in caplog.text
