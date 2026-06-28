import copy
import errno
import json
import tomllib

import pytest
import yaml

from exosphere import config as config_module
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

    @pytest.mark.parametrize("content", ["", "   \n  \n"], ids=["empty", "whitespace"])
    @pytest.mark.parametrize(
        "suffix, loader",
        [
            (".yaml", yaml.safe_load),
            (".toml", tomllib.load),
            (".json", json.load),
        ],
        ids=["yaml", "toml", "json"],
    )
    def test_from_file_empty_is_noop(
        self, tmp_path, config_defaults, caplog, suffix, loader, content
    ):
        """
        Ensure that an empty/whitespace-only source file is not harmful

        The config is expected to remain with the default values, and a
        warning should be logged. None of the known loaders handle this
        the same, so this guards against Weird Shit(tm), and this whole
        scenario should essentially be a no-op.
        """
        import logging

        empty_file = tmp_path / f"empty{suffix}"
        empty_file.write_text(content)

        config = Configuration()
        with caplog.at_level(logging.WARNING):
            result = config.from_file(str(empty_file), loader)

        assert result is True
        assert config == config_defaults
        assert "empty" in caplog.text.casefold()

    @pytest.mark.parametrize(
        "content",
        ["- a\n- b\n", "42\n"],
        ids=["list", "scalar"],
    )
    def test_from_file_non_mapping_raises(self, tmp_path, content):
        """
        A top-level non-mapping (list/scalar) raises a clear error naming
        the real problem, rather than an opaque unpacking failure deeper in
        update_from_mapping.
        """
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(content)

        config = Configuration()
        with pytest.raises(ValueError, match="must contain a mapping"):
            config.from_file(str(bad_file), yaml.safe_load)

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

    def test_update_from_env_nested_dicts_ignored(self, monkeypatch, caplog):
        """
        Unknown nested level keys in environment variables are ignored.

        We currently don't make use of these structures in the options
        schema yet, but they are supported by the Configuration system.

        Env overrides are applied best-effort, so an unknown nested key does
        not abort: the whole subtree is dropped with a warning, leaving the
        rest of the configuration valid.

        This should be revisited if we ever add nested dicts to the schema.
        """
        # Mock environment variables for nested dict structure
        monkeypatch.setenv("EXOSPHERE_OPTIONS_NESTED__LEVEL1__KEY1", "value1")

        config = Configuration()

        with caplog.at_level("WARNING"):
            result = config.from_env()

        assert result is True
        assert "nested" not in config["options"]
        assert "nested subtree dropped" in caplog.text

    def test_update_from_env_invalid_value_ignored(self, monkeypatch, caplog):
        """Bad values from env are ignored, rest of config valid"""
        monkeypatch.setenv("EXOSPHERE_OPTIONS_MAX_THREADS", "7")  # yes
        monkeypatch.setenv("EXOSPHERE_OPTIONS_LOG_LEVEL", "BERSERK")  # NO!

        config = Configuration()

        with caplog.at_level("WARNING"):
            result = config.from_env()

        assert result is True
        assert config["options"]["max_threads"] == 7
        assert config["options"]["log_level"] == config.DEFAULTS["options"]["log_level"]
        assert "Ignoring invalid environment override for 'log_level'" in caplog.text

    def test_update_from_mapping_rolls_back_on_invalid(self):
        """Failed validation does not leave config partially updated"""
        config = Configuration()
        before = copy.deepcopy(dict(config))

        with pytest.raises(ValueError):
            config.update_from_mapping({"options": {"max_threads": "not a number"}})

        assert dict(config) == before

    def test_update_from_mapping_rolls_back_hosts_on_invalid(self):
        """A hosts-section validation failure restores the prior hosts list."""
        config = Configuration()
        config.update_from_mapping({"hosts": [{"name": "keep", "ip": "10.0.0.1"}]})
        before = copy.deepcopy(config["hosts"])

        # Duplicate names fail at the ConfigModel level; the prior hosts list
        # must be left intact rather than replaced by the rejected one.
        with pytest.raises(ValueError, match="Duplicate host names"):
            config.update_from_mapping(
                {"hosts": [{"name": "dup", "ip": "1"}, {"name": "dup", "ip": "2"}]}
            )

        assert config["hosts"] == before

    def test_from_env_keeps_interdependent_overrides_together(
        self, monkeypatch, caplog
    ):
        """A pair of related overrides are not dropped by an unrelated invalid key"""

        # reap<=lifetime holds for 400<=600, but only if applied together
        monkeypatch.setenv("EXOSPHERE_OPTIONS_SSH_PIPELINING_REAP_INTERVAL", "400")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_SSH_PIPELINING_LIFETIME", "600")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_LOG_LEVEL", "BOGUS")  # the real culprit

        config = Configuration()
        with caplog.at_level("WARNING"):
            config.from_env()

        # The boys are still here, gloriously valid together
        assert config["options"]["ssh_pipelining_reap_interval"] == 400
        assert config["options"]["ssh_pipelining_lifetime"] == 600
        # And the paste eating entry isn't
        assert config["options"]["log_level"] == config.DEFAULTS["options"]["log_level"]
        assert "log_level" in caplog.text

    def test_from_env_drops_genuine_cross_field_conflict(self, monkeypatch):
        """
        Related overrides that are invalid as a pair are dropped wholesale.

        This is a corner case, but in the scenario where two related
        overrides have a mutual constraint, and they are both present
        but violate the constraint, we don't apply either of them and
        drop them as a package deal.
        """

        # interval >= lifetime, a nonsensical configuration
        monkeypatch.setenv("EXOSPHERE_OPTIONS_SSH_PIPELINING_REAP_INTERVAL", "900")
        monkeypatch.setenv("EXOSPHERE_OPTIONS_SSH_PIPELINING_LIFETIME", "500")

        config = Configuration()
        result = config.from_env()

        # Did not abort, and both overrides reverted to their defaults
        assert result is True
        assert (
            config["options"]["ssh_pipelining_reap_interval"]
            == config.DEFAULTS["options"]["ssh_pipelining_reap_interval"]
        )
        assert (
            config["options"]["ssh_pipelining_lifetime"]
            == config.DEFAULTS["options"]["ssh_pipelining_lifetime"]
        )

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
        Ensure that update_from_mapping merges the option section
        rather than replace it wholesale.
        """
        config = Configuration()

        # First update sets one option
        config.update_from_mapping({"options": {"log_level": "DEBUG"}})
        # Second update sets a different option
        config.update_from_mapping({"options": {"max_threads": 42}})

        # Both updates survive (deep merge, not replacement)
        assert config["options"]["log_level"] == "DEBUG"
        assert config["options"]["max_threads"] == 42

        # Ensure other default options are still present and untouched
        assert config["options"]["debug"] is False
        assert "cache_file" in config["options"]


class TestSchemaValidation:
    """Test suite for config schema validation and related behaviors."""

    def test_host_model_mirrors_host_constructor(self):
        """
        HostModel must match the Host object constructor at all times

        Most of our instantiation code simply dumps it wholesale into the
        Host constructor as kwargs, so they should not drift.
        """
        import inspect

        from exosphere.config import HostModel
        from exosphere.objects import Host

        ctor_params = {
            name
            for name in inspect.signature(Host.__init__).parameters
            if name != "self"
        }

        assert set(HostModel.model_fields) == ctor_params

    def test_defaults_derived_from_options_model(self):
        """Class option defaults are the canonical dump of OptionsModel."""
        from exosphere.config import OptionsModel

        assert Configuration.DEFAULTS["options"] == OptionsModel().model_dump()

    def test_unknown_option_is_rejected(self):
        """Unknown option keys hard fail with a ValueError"""
        config = Configuration()

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            config.update_from_mapping({"options": {"max_trheads": 4}})

    def test_deprecated_option_is_dropped_with_warning(self, mocker, caplog):
        """Deprecated options are tolerated but dropped"""
        from exosphere.config import OptionsModel

        mocker.patch.dict(
            OptionsModel.DEPRECATED_OPTIONS,
            {"legacy_option": "removed in 4.2.0; use modern_option instead"},
        )

        config = Configuration()

        with caplog.at_level("WARNING"):
            result = config.update_from_mapping({"options": {"legacy_option": 123}})

        assert result is True
        # The deprecated key is dropped, not retained
        assert "legacy_option" not in config["options"]
        # And a warning naming it (and the migration note) is logged
        assert "legacy_option" in caplog.text
        assert "removed in 4.2.0; use modern_option instead" in caplog.text

    @pytest.mark.parametrize("backup_count", [0, -5])
    def test_log_backup_count_below_one_rejected(self, backup_count):
        """
        Log backup count must be >=1
        Otherwise, the rotating file handler will just disable rotation
        entirely, which is surprising, and counterproductive.
        """
        config = Configuration()

        with pytest.raises(ValueError, match="greater than or equal to 1"):
            config.update_from_mapping({"options": {"log_backup_count": backup_count}})

    @pytest.mark.parametrize(
        "mapping",
        [
            {"hosts": [{"name": "", "ip": "127.0.0.1"}]},
            {"hosts": [{"name": "   ", "ip": "127.0.0.1"}]},
            {"hosts": [{"name": "a", "ip": ""}]},
            {"hosts": [{"name": "a", "ip": "127.0.0.1", "username": ""}]},
            {"options": {"default_username": ""}},
            {"options": {"editor": ""}},
        ],
        ids=["name", "name_ws", "ip", "host_user", "default_user", "editor"],
    )
    def test_empty_string_fields_rejected(self, mapping):
        """
        Identifier/credential string fields reject empty or whitespace-only
        values rather than silently accepting them.
        """
        config = Configuration()

        with pytest.raises(ValueError, match="should have at least 1 character"):
            config.update_from_mapping(mapping)

    @pytest.mark.parametrize(
        "bad_locale",
        ["C; rm -rf /", "en_US.UTF-8 extra", "C && evil", "$(evil)", "C|x"],
        ids=["semicolon", "space", "and", "subshell", "pipe"],
    )
    def test_ssh_locale_rejects_shell_unsafe_values(self, bad_locale):
        """
        Locale options are exported verbatim into a remote shell command, so
        values with shell metacharacters or whitespace are rejected outright.
        """
        config = Configuration()

        with pytest.raises(ValueError, match="should match pattern"):
            config.update_from_mapping({"options": {"default_ssh_locale": bad_locale}})

        with pytest.raises(ValueError, match="should match pattern"):
            config.update_from_mapping(
                {"hosts": [{"name": "a", "ip": "h", "ssh_locale": bad_locale}]}
            )

    @pytest.mark.parametrize(
        "good_locale",
        ["C", "POSIX", "C.UTF-8", "en_US.UTF-8", "de_DE.UTF-8@euro", "  C.UTF-8  "],
    )
    def test_ssh_locale_accepts_valid_values(self, good_locale):
        """Valid locale names are accepted, with surrounding whitespace stripped."""
        config = Configuration()

        config.update_from_mapping({"options": {"default_ssh_locale": good_locale}})

        assert config["options"]["default_ssh_locale"] == good_locale.strip()

    def test_identifier_whitespace_is_stripped(self):
        """Surrounding whitespace on name/ip is normalized away."""
        config = Configuration()

        config.update_from_mapping(
            {"hosts": [{"name": "  web1  ", "ip": "  10.0.0.1  "}]}
        )

        assert config["hosts"][0] == {"name": "web1", "ip": "10.0.0.1"}

    def test_duplicate_host_names_rejected(self):
        """Duplicate host names are rejected: the inventory requires unique names."""
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
            # Missing name: no name to show, so the list index is used
            (
                [{"ip": "127.0.0.4"}],
                r"hosts\.0\.name: Field required",
            ),
            # Missing ip: the host is identified by its name, not its index
            (
                [{"name": "host4"}],
                r"hosts\.host4\.ip: Field required",
            ),
            # Invalid characters in fields
            (
                [{"name": "host1", "ip": "user@127.0.0.1"}],
                "'@' character is not allowed in hostname or ip",
            ),
        ],
        ids=["missing_name", "missing_ip", "at_in_ip"],
    )
    def test_host_field_validation_errors(self, hosts_data, expected_error_match):
        """
        Host entries raise an appropriate ValueError for missing required
        fields and for an '@' in the ip field.
        """
        config = Configuration()

        with pytest.raises(ValueError, match=expected_error_match):
            config.update_from_mapping({"hosts": hosts_data})

    def test_host_error_identifies_host_by_name(self):
        """
        A field error on one host among many is located by the host's name,
        not its list index, so operators can find it without counting entries.
        """
        config = Configuration()

        with pytest.raises(ValueError, match=r"hosts\.web3\.ip: Field required"):
            config.update_from_mapping(
                {
                    "hosts": [
                        {"name": "web1", "ip": "10.0.0.1"},
                        {"name": "web2", "ip": "10.0.0.2"},
                        {"name": "web3"},  # missing ip, third in the list
                    ]
                }
            )

    @pytest.mark.parametrize("port", [0, 65536])
    def test_host_port_out_of_range_rejected(self, port):
        """Port must be within 1-65535."""
        config = Configuration()

        with pytest.raises(ValueError, match="hosts.a.port"):
            config.update_from_mapping(
                {"hosts": [{"name": "a", "ip": "h", "port": port}]}
            )

    @pytest.mark.parametrize("port", [1, 65535])
    def test_host_port_boundaries_accepted(self, port):
        """The 1 and 65535 boundaries are valid ports."""
        config = Configuration()

        config.update_from_mapping({"hosts": [{"name": "a", "ip": "h", "port": port}]})

        assert config["hosts"][0]["port"] == port

    @pytest.mark.parametrize(
        "given,expected",
        [("NOPASSWD", "nopasswd"), ("Skip", "skip"), ("SKIP", "skip")],
    )
    def test_sudo_policy_normalized_case_insensitively(self, given, expected):
        """Sudo policies are accepted in any case and stored lowercased."""
        config = Configuration()

        config.update_from_mapping(
            {
                "options": {"default_sudo_policy": given},
                "hosts": [{"name": "a", "ip": "h", "sudo_policy": given}],
            }
        )

        assert config["options"]["default_sudo_policy"] == expected
        assert config["hosts"][0]["sudo_policy"] == expected

    def test_unknown_host_key_dropped_with_warning(self, caplog):
        """
        Unknown keys in a host entry are dropped with a warning
        We don't hard fail to be reasonably forward compatible, and
        we should be more forgiving towards big inventories.
        """
        config = Configuration()

        with caplog.at_level("WARNING"):
            result = config.update_from_mapping(
                {"hosts": [{"name": "host1", "ip": "127.0.0.1", "wrong_key": "oops"}]}
            )

        assert result is True
        # Unknown key is dropped from the normalized host entry
        assert "typo" not in config["hosts"][0]
        assert config["hosts"][0] == {"name": "host1", "ip": "127.0.0.1"}
        # And a warning is logged naming the offending key and host
        # Long enough have we stood by and watched ourselves not
        # include WHAT generated the error as part of the error.
        assert (
            "Unknown host configuration option 'wrong_key' for host 'host1'"
            in caplog.text
        )


class TestKnownLoaders:
    """Tests for the KNOWN_LOADERS mapping."""

    def test_covers_standard_extensions(self):
        for ext in ("yaml", "yml", "toml", "json"):
            assert ext in config_module.KNOWN_LOADERS

    def test_yaml_and_yml_share_loader(self):
        assert config_module.KNOWN_LOADERS["yaml"] is config_module.KNOWN_LOADERS["yml"]


class TestValidate:
    """Tests for the module-level config.validate helper."""

    def test_valid_file_passes(self, tmp_path):
        target = tmp_path / "config.yaml"
        target.write_text("options:\n  debug: true\n")

        # Should not raise
        assert config_module.validate(target) is None

    def test_empty_file_is_valid(self, tmp_path):
        """Empty config file should be valid, and use defaults"""
        target = tmp_path / "config.yaml"
        target.write_text("")

        # Should not raise (empty YAML parses to None)
        assert config_module.validate(target) is None

    def test_comment_only_file_is_valid(self, tmp_path):
        """A comment-only config file is also just as valid"""
        target = tmp_path / "config.yaml"
        target.write_text("# just a comment, no settings\n")

        assert config_module.validate(target) is None

    def test_invalid_host_raises(self, tmp_path):
        target = tmp_path / "config.yaml"
        target.write_text("hosts:\n  - name: a\n")  # missing 'ip'

        with pytest.raises(ValueError):
            config_module.validate(target)

    def test_malformed_file_raises(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text("{ not valid json")

        with pytest.raises(Exception):
            config_module.validate(target)

    def test_non_mapping_raises(self, tmp_path):
        """A top-level non-mapping config reports the real problem clearly."""
        # This test is yaml-specific but it is the easiest way
        # to express this mistake in the context of the test
        target = tmp_path / "config.yaml"
        target.write_text("- a\n- b\n")  # a list, not a mapping

        with pytest.raises(ValueError, match="must contain a mapping"):
            config_module.validate(target)

    def test_unknown_extension_raises(self, tmp_path):
        target = tmp_path / "config.cfg"
        target.write_text("whatever")

        with pytest.raises(ValueError, match="Unknown configuration file extension"):
            config_module.validate(target)

    def test_does_not_mutate_app_config(self, tmp_path, mocker):
        """validate never touches the real, global app_config"""
        spy = mocker.patch.object(Configuration, "from_file", autospec=True)
        target = tmp_path / "config.yaml"
        target.write_text("options:\n  debug: true\n")

        config_module.validate(target)

        # from_file was called on a fresh instance, not the global app_config
        called_instance = spy.call_args.args[0]
        from exosphere import app_config

        assert called_instance is not app_config
