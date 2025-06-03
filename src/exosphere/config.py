import errno
import json
import logging
import tomllib
from collections.abc import Callable
from typing import BinaryIO

import yaml


class Configuration(dict):
    """
    Hold configuration values for the application.
    Extends a native dict to store the global options section of the
    inventory toml file.
    """

    DEFAULTS: dict = {
        "options": {
            "debug": False,  # Debug mode, enable verbose on root logger
            "log_level": "INFO",  # Default log level for the application
            "log_file": "exosphere.log",  # Default log file for the application
            "cache_autosave": True,  # Automatically save cache to disk after changes
            "cache_file": "exosphere.db",  # Default cache file for the application
            "stale_threshold": 86400,  # How long before a host is considered stale (in seconds)
            "default_timeout": 10,  # Default ssh connection timeout (in seconds)
            "max_threads": 15,  # Maximum number of threads to use for parallel operations
        },
        "hosts": [],
    }

    def __init__(self) -> None:
        """
        Initialize the Configuration object with default values.
        """
        dict.__init__(self, self.DEFAULTS)
        self.logger = logging.getLogger(__name__)

    def from_toml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a toml file

        This method is a convenience wrapper used for shorthand
        for the from_file method, with tomllib.load() as the loader.

        see `from_file()`for details.
        """
        return self.from_file(filepath, tomllib.load, silent=silent)

    def from_yaml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a yaml file

        This method is a convenience wrapper used for shorthand
        for the from_file method, with yaml.safe_load() as the loader.

        see `from_file()`for details.
        """
        return self.from_file(filepath, yaml.safe_load, silent=silent)

    def from_json(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a json file

        This method is a convenience wrapper used for shorthand
        for the from_file method, with json.load() as the loader.

        see `from_file()`for details.
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

        For instance, tomllib.load() is a valid loader for toml files

        This allows for the format of the configuration file to be
        essentially decoupled from the validation and internal
        representation of the data.
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
        Populate values like the native dict.update() method, but
        only if the key is a valid root configuration key.

        This will also deep merge the values from the mapping
        if they are also dicts.
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
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self.deep_update(d[k], v)
            else:
                d[k] = v
        return d
