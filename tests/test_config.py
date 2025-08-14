import copy
import errno
import json
import tomllib

import pytest
import yaml

from exosphere.config import Configuration


class TestConfiguration:
    @pytest.fixture()
    def config_defaults(self):
        return Configuration.DEFAULTS

    @pytest.fixture()
    def expected_config(self):
        data = copy.deepcopy(Configuration.DEFAULTS)

        data["options"]["log_level"] = "DEBUG"
        data["options"]["debug"] = True

        data["hosts"] = [
            {"name": "host1", "ip": "127.0.0.1"},
            {"name": "host2", "ip": "127.0.0.2", "port": 22},
            {"name": "host3", "ip": "127.0.0.3", "description": "Test Host"},
        ]

        return data

    @pytest.fixture()
    def toml_config_file(self, tmp_path):
        toml_content = """
        [options]
        log_level = "DEBUG"
        debug = true
        
        [[hosts]]
        name = "host1"
        ip = "127.0.0.1"

        [[hosts]]
        name = "host2"
        ip = "127.0.0.2"
        port = 22

        [[hosts]]
        name = "host3"
        ip = "127.0.0.3"
        description = "Test Host"
        """

        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)
        return config_file

    @pytest.fixture()
    def yaml_config_file(self, tmp_path):
        yaml_content = """
        options:
          log_level: DEBUG
          debug: true
        hosts:
          - name: host1
            ip: 127.0.0.1
          - name: host2
            ip: 127.0.0.2
            port: 22
          - name: host3
            ip: 127.0.0.3
            description: Test Host
        """

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)
        return config_file

    @pytest.fixture()
    def json_config_file(self, tmp_path):
        json_content = """
        {
            "options": {
                "log_level": "DEBUG",
                "debug": true
            },
            "hosts": [
                {
                    "name": "host1",
                    "ip": "127.0.0.1"
                },
                {
                    "name": "host2",
                    "ip": "127.0.0.2",
                    "port": 22
                },
                {
                    "name": "host3",
                    "ip": "127.0.0.3",
                    "description": "Test Host"
                }
            ]
        }
        """
        config_file = tmp_path / "config.json"
        config_file.write_text(json_content)
        return config_file

    @pytest.fixture()
    def toml_config_file_extra(self, tmp_path):
        toml_content = """
        [options]
        log_level = "DEBUG"
        debug = true
        
        [[hosts]]
        name = "host1"
        ip = "127.0.0.1"

        [[hosts]]
        name = "host2"
        ip = "127.0.0.2"
        port = 22

        [[hosts]]
        name = "host3"
        ip = "127.0.0.3"
        description = "Test Host"

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
          debug: true
        hosts:
          - name: host1
            ip: 127.0.0.1
          - name: host2
            ip: 127.0.0.2
            port: 22
          - name: host3
            ip: 127.0.0.3
            description: Test Host
        unrecognized_section:
          name: extra
          description: This is an unparsed section
        """

        config_file = tmp_path / "config_extra.yaml"
        config_file.write_text(yaml_content)
        return config_file

    @pytest.fixture()
    def json_config_file_extra(self, tmp_path):
        json_content = """
        {
            "options": {
                "log_level": "DEBUG",
                "debug": true
            },
            "hosts": [
                {
                    "name": "host1",
                    "ip": "127.0.0.1"
                },
                {
                    "name": "host2",
                    "ip": "127.0.0.2",
                    "port": 22
                },
                {
                    "name": "host3",
                    "ip": "127.0.0.3",
                    "description": "Test Host"
                }
            ],
            "unrecognized_section": {
                "name": "extra",
                "description": "This is an unparsed section"
            }
        }
        """
        config_file = tmp_path / "config_extra.json"
        config_file.write_text(json_content)
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
        """
        Ensure that the Configuration object can be populated
        from a yaml file.
        """
        config = Configuration()

        assert config.from_yaml(yaml_config_file) is True

        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

    def test_from_json(self, json_config_file, expected_config):
        """
        Ensure that the Configuration object can be populated
        from a json file.
        """
        config = Configuration()

        assert config.from_json(json_config_file) is True

        for key in expected_config:
            assert key in config
            assert config[key] == expected_config[key]

    @pytest.mark.parametrize(
        "config_file, loader",
        [
            ("toml_config_file", tomllib.load),
            ("yaml_config_file", yaml.safe_load),
            ("json_config_file", json.load),
        ],
        ids=["toml", "yaml", "json"],
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
            (json.load),
        ],
        ids=["toml", "yaml", "json"],
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
            ("json_config_file_extra", json.load),
        ],
        ids=["toml", "yaml", "json"],
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
        mocker.patch("exosphere.config.open", side_effect=exception_type)

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
            "exosphere.config.open", side_effect=OSError(error_code, error_name)
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
                {"name": "host5", "ip": "172.16.64.5", "description": "New Host"},
            ],
            "invalid_key": [{"name": "invalid"}],
        }
        result = config.update_from_mapping(new_mapping)

        assert result is True

        assert config["options"]["log_level"] == "INFO"
        assert len(config["hosts"]) == 3
        assert config["hosts"][0]["name"] == "host3"
        assert config["hosts"][1]["name"] == "host4"
        assert config["hosts"][2]["name"] == "host5"
        assert config["hosts"][0]["ip"] == "172.16.64.3"
        assert config["hosts"][1]["ip"] == "172.16.64.4"
        assert config["hosts"][2]["ip"] == "172.16.64.5"
        assert config["hosts"][1]["port"] == 22
        assert config["hosts"][2]["description"] == "New Host"

        assert "invalid_key" not in config
        assert "is not a valid root key" in caplog.text

    def test_update_from_mapping_maintains_defaults(self, mocker, config_defaults):
        """
        Ensure that the Configuration object maintains default values
        when updating from a mapping.
        """

        new_mapping = {
            "options": {"log_level": "INFO"},
            "hosts": [
                {"name": "host3", "ip": "127.0.0.3"},
            ],
        }

        config = Configuration()
        config.update_from_mapping(new_mapping)

        # Check that the options dicts have the same keys
        assert set(config["options"].keys()) == set(config_defaults["options"].keys())
        # Check that one of our unconfigured options is still the default
        assert config["options"]["debug"] == config_defaults["options"]["debug"]

    def test_update_from_mapping_invalid_length(self):
        """
        Ensure that the Configuration object raises a TypeError
        when more than one positional argument is passed to
        update_from_mapping.
        """
        config = Configuration()

        with pytest.raises(TypeError):
            config.update_from_mapping({}, {}, {})

    def test_update_from_mapping_unique_constraints(self):
        """
        Ensure that the Configuration object raises a ValueError
        when duplicate host names are found in the configuration.
        """
        config = Configuration()

        with pytest.raises(ValueError, match="Duplicate host names found"):
            config.update_from_mapping(
                {
                    "hosts": [
                        {"name": "host1", "ip": "127.0.0.4"},
                        {"name": "host1", "ip": "172.0.0.3"},
                    ]
                }
            )

    @pytest.mark.parametrize(
        "hosts_data,expected_error_match",
        [
            # Missing required fields
            (
                [{"ip": "127.0.0.4"}],
                "missing required 'name' field",
            ),
            (
                [{"name": "host4"}],
                "missing required 'ip' field",
            ),
            # Invalid characters in fields
            (
                [{"name": "host1", "ip": "user@127.0.0.1"}],
                "invalid hostname or ip.*'@' character is not allowed",
            ),
        ],
        ids=["missing_name", "missing_ip", "at_in_ip"],
    )
    def test_update_from_mapping_validation_errors(
        self, hosts_data, expected_error_match
    ):
        """
        Ensure that the configuration object raises appropriate ValueError
        for various validation failures in the host section.
        """
        config = Configuration()

        with pytest.raises(ValueError, match=expected_error_match):
            config.update_from_mapping({"hosts": hosts_data})

    def test_update_from_env(self, mocker, monkeypatch):
        """
        Ensure that the Configuration object can be updated
        from environment variables.
        """
        # Mock environment variables
        monkeypatch.setenv("EXOSPHERE_OPTIONS_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_DEBUG", "true")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_CACHE_FILE", "bigtest.db")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_MAX_THREADS", "8")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_DEFAULT_USERNAME", "testuser")

        config = Configuration()
        result = config.from_env()

        assert result is True
        assert config["options"]["log_level"] == "DEBUG"
        assert config["options"]["debug"] is True
        assert config["options"]["cache_file"] == "bigtest.db"
        assert config["options"]["max_threads"] == 8
        assert config["options"]["default_username"] == "testuser"

    def test_update_from_env_invalid_key(self, mocker, monkeypatch, caplog):
        """
        Ensure that the Configuration object logs a warning
        when an invalid environment variable key is encountered.
        """
        # Mock environment variables
        monkeypatch.setenv("EXOSPHERE_OPTIONS_INVALID_KEY", "some_value")

        config = Configuration()
        result = config.from_env()

        assert result is True
        assert "invalid_key" not in config["options"]
        assert "is not a valid options key" in caplog.text

    def test_update_from_env_nested_dicts(self, mocker, monkeypatch):
        """
        Ensure that the Configuration object can be updated
        from environment variables with nested dictionaries using
        double underscore (__) as a separator.
        """
        # Mock environment variables for nested dict structure
        monkeypatch.setenv("EXOSPHERE_OPTIONS_NESTED__LEVEL1__KEY1", "value1")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_NESTED__LEVEL1__KEY2", "42")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_NESTED__LEVEL2__SUBKEY", "true")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_DEEP__VERY__NESTED__KEY", "deep_value")

        config = Configuration()
        result = config.from_env()

        assert result is True

        # Check nested structure was created correctly
        assert "nested" in config["options"]
        assert "level1" in config["options"]["nested"]
        assert "level2" in config["options"]["nested"]
        assert config["options"]["nested"]["level1"]["key1"] == "value1"
        assert config["options"]["nested"]["level1"]["key2"] == 42
        assert config["options"]["nested"]["level2"]["subkey"] is True

        # Check deeply nested structure
        assert "deep" in config["options"]
        assert "very" in config["options"]["deep"]
        assert "nested" in config["options"]["deep"]["very"]
        assert config["options"]["deep"]["very"]["nested"]["key"] == "deep_value"

    def test_update_from_env_nested_dicts_custom_parser(self, mocker, monkeypatch):
        """
        Ensure that nested dicts work with custom parsers in from_env.
        """

        # Use a simple parser that just converts to uppercase
        def uppercase_parser(value):
            return value.upper()

        monkeypatch.setenv("EXOSPHERE_OPTIONS_CUSTOM__NESTED__VALUE", "lowercase")

        config = Configuration()
        result = config.from_env(parser=uppercase_parser)

        assert result is True
        assert config["options"]["custom"]["nested"]["value"] == "LOWERCASE"

    def test_deep_update_simple_merge(self):
        """
        Ensure that deep_update correctly merges nested dictionaries
        without replacing the entire structure.
        """
        config = Configuration()

        # Set up initial nested structure
        config["options"]["existing"] = {
            "keep_this": "original_value",
            "update_this": "old_value",
            "nested": {"deep_keep": "deep_original", "deep_update": "deep_old"},
        }

        # Update with new nested structure
        update_dict = {
            "existing": {
                "update_this": "new_value",
                "add_this": "added_value",
                "nested": {"deep_update": "deep_new", "deep_add": "deep_added"},
            }
        }

        config.deep_update(config["options"], update_dict)

        # Check that existing values were preserved
        assert config["options"]["existing"]["keep_this"] == "original_value"
        assert config["options"]["existing"]["nested"]["deep_keep"] == "deep_original"

        # Check that values were updated
        assert config["options"]["existing"]["update_this"] == "new_value"
        assert config["options"]["existing"]["nested"]["deep_update"] == "deep_new"

        # Check that new values were added
        assert config["options"]["existing"]["add_this"] == "added_value"
        assert config["options"]["existing"]["nested"]["deep_add"] == "deep_added"

    def test_deep_update_deeply_nested(self):
        """
        Ensure that deep_update works recursively for multiple levels
        of nested dictionaries.
        """
        config = Configuration()

        # Create a deeply nested structure
        target = {
            "level1": {
                "level2": {
                    "level3": {
                        "existing": "original",
                        "level4": {"deep_existing": "deep_original"},
                    }
                }
            }
        }

        # Update with another deeply nested structure
        update = {
            "level1": {
                "level2": {
                    "level3": {
                        "new_key": "new_value",
                        "level4": {
                            "deep_existing": "deep_updated",
                            "deep_new": "deep_new_value",
                        },
                    }
                }
            }
        }

        result = config.deep_update(target, update)

        # Check the method returns the updated dict
        assert result is target

        # Check deep preservation and updates
        assert target["level1"]["level2"]["level3"]["existing"] == "original"
        assert target["level1"]["level2"]["level3"]["new_key"] == "new_value"
        assert (
            target["level1"]["level2"]["level3"]["level4"]["deep_existing"]
            == "deep_updated"
        )
        assert (
            target["level1"]["level2"]["level3"]["level4"]["deep_new"]
            == "deep_new_value"
        )

    def test_deep_update_non_dict_replacement(self):
        """
        Ensure that deep_update replaces non-dict values with dict values
        and vice versa, rather than trying to merge incompatible types.
        """
        config = Configuration()

        target = {
            "string_to_dict": "original_string",
            "dict_to_string": {"key": "value"},
            "dict_merge": {"keep": "this", "replace": "old"},
        }

        update = {
            "string_to_dict": {"new": "dict_value"},
            "dict_to_string": "new_string",
            "dict_merge": {"replace": "new", "add": "added"},
        }

        config.deep_update(target, update)

        # Non-dict to dict replacement
        assert target["string_to_dict"] == {"new": "dict_value"}

        # Dict to non-dict replacement
        assert target["dict_to_string"] == "new_string"

        # Dict to dict merge
        assert target["dict_merge"]["keep"] == "this"
        assert target["dict_merge"]["replace"] == "new"
        assert target["dict_merge"]["add"] == "added"

    def test_update_from_mapping_uses_deep_update(self):
        """
        Ensure that update_from_mapping correctly uses deep_update
        for nested dictionary structures.
        """
        config = Configuration()

        # Set up initial state with nested options
        config["options"]["custom_section"] = {
            "existing_key": "original",
            "nested": {"deep_key": "deep_original"},
        }

        # Update with overlapping nested structure
        mapping = {
            "options": {
                "log_level": "DEBUG",  # Update existing top-level key
                "custom_section": {
                    "existing_key": "updated",  # Update existing nested key
                    "new_key": "added",  # Add new nested key
                    "nested": {
                        "deep_key": "deep_updated",  # Update deep nested key
                        "deep_new": "deep_added",  # Add new deep nested key
                    },
                },
            }
        }

        result = config.update_from_mapping(mapping)
        assert result is True

        # Check that deep_update was used (values were merged, not replaced)
        assert config["options"]["log_level"] == "DEBUG"
        assert config["options"]["custom_section"]["existing_key"] == "updated"
        assert config["options"]["custom_section"]["new_key"] == "added"
        assert (
            config["options"]["custom_section"]["nested"]["deep_key"] == "deep_updated"
        )
        assert config["options"]["custom_section"]["nested"]["deep_new"] == "deep_added"

        # Ensure other default options are still present
        assert "debug" in config["options"]
        assert "cache_file" in config["options"]
