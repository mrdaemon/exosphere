import copy
import errno
import json
import logging
import os
import tomllib
from collections.abc import Callable
from typing import Any, BinaryIO

import yaml

from exosphere import fspaths


class Configuration(dict):
    """
    Hold configuration values for the application.
    Extends a native dict to store the global options section of the
    inventory toml file.

    Has the following peculiarities vs a native dict:

    - Has many ``from_*`` methods to populate itself from various
      sources such as environment variables, files of various formats
    - Enforces a set of default values for the nested ``options`` dict
    - Enforces unicity for name keys in the ``hosts`` dict.
    - Has a :meth:`deep_update` method to recursively update nested dicts
      without replacing them entirely.

    This configuration structure is strongly inspired by the one used
    by Flask, because good things are worth replicating.
    """

    #: Default configuration values
    #: This dict contains the default configuration and is always
    #: used as a base for what the configuration object contains.
    #: This can be accessed to get the default values for any config key
    DEFAULTS: dict[str, Any] = {
        "options": {
            "debug": False,  # Debug mode, enable verbose on root logger
            "log_level": "INFO",  # Default log level for the application
            "log_file": str(
                fspaths.LOG_DIR / "exosphere.log"
            ),  # Default log file for the application
            "history_file": str(
                fspaths.STATE_DIR / "repl_history"
            ),  # Default history file for the repl
            "cache_autosave": True,  # Automatically save cache to disk after changes
            "cache_autopurge": True,  # Automatically purge hosts removed from inventory
            "cache_file": str(
                fspaths.STATE_DIR / "exosphere.db"
            ),  # Default cache file for the application
            "stale_threshold": 86400,  # How long before a host is considered stale
            "default_timeout": 10,  # Default ssh connection timeout (in seconds)
            "default_username": None,  # Default global username to use for SSH
            "default_sudo_policy": "skip",  # Global sudo policy for package manager ops
            "max_threads": 15,  # Maximum number of threads to use for parallel ops
        },
        "hosts": [],
    }

    def __init__(self) -> None:
        """
        Initialize the Configuration object with default values.

        The default values are a deep copy of the DEFAULTS dict,
        ensuring that the original DEFAULTS remains unchanged.
        """
        dict.__init__(self, copy.deepcopy(self.DEFAULTS))
        self.logger = logging.getLogger(__name__)

    def from_env(
        self,
        prefix: str = "EXOSPHERE_OPTIONS",
        parser: Callable[[str], Any] = json.loads,
    ) -> bool:
        """
        Populate the configuration structure from environment variables.

        Any environment variable that starts with the specified prefix
        (e.g., ``EXOSPHERE_OPTIONS_*``) will be considered for updating
        the configuration.

        Note that this is, currently, limited to the `options` section
        of the configuration. The inventory cannot be updated this way.

        If there are any nested dictionaries in the configuration,
        you can specify them using a double underscore (``__``) to
        separate the keys.

        The values for the keys are parsed as JSON types by default,
        but you can specify a custom loader function to parse the values,
        as long as it operates on strings.

        :param prefix: The prefix to look for in environment variables
        :param loader: A callable that takes a string and returns a parsed value
        :return: True if the configuration was successfully updated
        """
        prefix = prefix.upper() + "_"

        for key in os.environ:
            if not key.startswith(prefix):
                continue

            value = os.environ[key]
            key = key.removeprefix(prefix).lower()

            try:
                value = parser(value)
            except Exception:
                self.logger.debug(
                    "Could not parse environment variable %s: %s, keeping as string",
                    key,
                    value,
                )

            if "__" not in key:
                # Not a nested key, update
                if key in self.DEFAULTS["options"]:
                    self.logger.debug(
                        "Updating configuration key from env %s: %s", key, value
                    )
                    self["options"][key] = value
                else:
                    self.logger.warning(
                        "Configuration key %s is not a valid options key, ignoring", key
                    )
                continue

            # We have a nested key
            current = self["options"]
            *parent_keys, leaf_key = key.split("__")

            for parent in parent_keys:
                # Create nested dict if it doesn't exist
                if parent not in current:
                    current[parent] = {}

                current = current[parent]

            current[leaf_key] = value

        return True

    def from_toml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a toml file

        This method is a convenience wrapper used for shorthand
        for the from_file method, with `tomllib.load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the toml file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, tomllib.load, silent=silent)

    def from_yaml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a yaml file

        This method is a convenience wrapper used for shorthand
        for the `from_file` method, with `yaml.safe_load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the yaml file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, yaml.safe_load, silent=silent)

    def from_json(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a json file

        This method is a convenience wrapper used for shorthand
        for the `from_file` method, with `json.load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the json file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, json.load, silent=silent)

    def from_file(
        self, filepath: str, loader: Callable[[BinaryIO], dict], silent: bool = False
    ) -> bool:
        """
        Populate the configuration structure from a file, with a
        specified loader function callable.

        The loader must be a reference to a callable that takes a
        file handle and returns a mapping of the data contained within.

        For instance, `tomllib.load()` is a valid loader for toml files

        This allows for the format of the configuration file to be
        essentially decoupled from the validation and internal
        representation of the data.

        :param filepath: Path to the file to load
        :param loader: A callable that takes a file handle and returns a dict
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
        """
        try:
            with open(filepath, "rb") as f:
                data = loader(f)
        except IOError as e:
            if silent and e.errno in (errno.ENOENT, errno.EISDIR):
                return False

            e.strerror = f"Unable to load config file {filepath}: {e.strerror}"

            raise

        return self.update_from_mapping(data)

    def update_from_mapping(self, *mapping: dict, **kwargs: dict) -> bool:
        """
        Populate values like the native `dict.update()` method, but
        only if the key is a valid root configuration key.

        This will also deep merge the values from the mapping
        if they are also dicts.

        :param mapping: A single mapping to update the configuration with
        :param kwargs: Additional keyword arguments to update the configuration with
        :return: True if the configuration was successfully updated
        """
        mappings = []

        if len(mapping) == 1:
            if hasattr(mapping[0], "items"):
                mappings.append(mapping[0].items())
            else:
                mappings.append(mapping[0])
        elif len(mapping) > 1:
            raise TypeError(
                f"Config mapping expected at most 1 positional argument, "
                f"got {len(mapping)}"
            )

        mappings.append(kwargs.items())

        # Parse and filter mappings
        for mapping in mappings:
            for k, v in mapping:
                if k in self.DEFAULTS:
                    if isinstance(self[k], dict) and isinstance(v, dict):
                        # deep merge the dicts
                        self.deep_update(self[k], v)
                    else:
                        self[k] = v
                else:
                    self.logger.warning(
                        "Configuration key %s is not a valid root key, ignoring", k
                    )

        # uniqueness constraint for host names
        hosts = self.get("hosts", [])
        if isinstance(hosts, list):
            names: list[str] = [
                str(host.get("name"))
                for host in hosts
                if isinstance(host, dict) and "name" in host
            ]
            dupes: set[str] = {str(name) for name in names if names.count(name) > 1}
            if dupes:
                msg = f"Duplicate host names found in configuration: {', '.join(dupes)}"
                raise ValueError(msg)

        return True

    def deep_update(self, d: dict, u: dict) -> dict:
        """
        Recursively update a dictionary with another dictionary.
        Ensures nested dicts are updated rather than replaced.

        :param d: The dictionary to update
        :param u: The dictionary with updates
        :return: The updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self.deep_update(d[k], v)
            else:
                d[k] = v
        return d
