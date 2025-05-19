import errno
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
            "log_level": "INFO",
        },
        "hosts": [],
    }

    VALID_ROOT_KEYS: list[str] = [
        "options",
        "hosts",
    ]

    def __init__(self):
        """
        Initialize the Configuration object with default values.
        """
        dict.__init__(self, self.DEFAULTS)

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
                if k in self.VALID_ROOT_KEYS:
                    self[k] = v

        return True
