import errno
import json
import logging
import tomllib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, BinaryIO, Generator, Optional

import yaml

from exosphere.objects import Host


class Configuration(dict):
    """
    Hold configuration values for the application.
    Extends a native dict to store the global options section of the
    inventory toml file.
    """

    DEFAULTS: dict = {
        "options": {
            "log_level": "INFO",
            "log_file": "exosphere.log",
            "debug": False,
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


class Inventory:
    """
    Inventory and state management

    Handles reading the inventory from file and creating the
    Host objects.

    Convenience methods for syncing, refreshing catalogs, updates and ping
    are provided, and are all parallelized using Threads.

    Runtime errors are generally non-fatal, but will be logged.
    The Host objects themselves usually handle their own failure cases
    and will log errors as appropriate, on top of flagging themselves
    as offline if they are unable to perform their tasks.
    """

    def __init__(self, config: Configuration) -> None:
        """
        Initialize the Inventory object with default values.
        """
        self.configuration = config
        self.hosts: list[Host] = []

        self.logger = logging.getLogger(__name__)

        self.init_all()

    def init_all(self) -> None:
        """
        Setup the inventory by creating Host objects from the
        configuration.

        Existing state will be cleared.
        """
        self.hosts: list[Host] = []

        if len(self.configuration["hosts"]) == 0:
            self.logger.warning("No hosts found in inventory")
            return

        self.logger.debug(
            "Initializing inventory with %d hosts", len(self.configuration["hosts"])
        )

        for host in self.configuration["hosts"]:
            try:
                host_obj = Host(**host)
            except Exception as e:
                self.logger.error(
                    "Unable to create host object from inventory: %s: %s", host, e
                )
                raise ValueError(
                    f"Unable to create host object from inventory: {host}: {e}"
                ) from e

            self.hosts.append(host_obj)

    def sync_all(self) -> None:
        """
        Sync all hosts in the inventory.

        """
        self.logger.info("Syncing all hosts in inventory")

        for host, _, exc in self.run_all(
            "sync",
        ):
            if exc:
                self.logger.error("Failed to sync host %s: %s", host.name, exc)
            else:
                self.logger.info("Host %s synced successfully", host.name)

        self.logger.info("All hosts synced")

    def refresh_catalog_all(self) -> None:
        """
        Refresh the package catalog on all hosts in the inventory.

        This method will call the `refresh_catalog` method on each
        Host object in the inventory.
        """
        self.logger.info("Refreshing package catalogs for all hosts")

        for host, _, exc in self.run_all(
            "refresh_catalog",
        ):
            if exc:
                self.logger.error(
                    "Failed to refresh package catalog for host %s: %s", host.name, exc
                )
            else:
                self.logger.info("Package catalog refreshed for host %s", host.name)

        self.logger.info("Package catalogs refreshed for all hosts")

    def refresh_updates_all(self) -> None:
        """
        Refresh the list of available updates on all hosts in the inventory.

        This method will call the `refresh_updates` method on each
        Host object in the inventory.
        """

        self.logger.info("Refreshing updates for all hosts")

        for host, _, exc in self.run_all(
            "refresh_updates",
        ):
            if exc:
                self.logger.error(
                    "Failed to refresh updates for host %s: %s", host.name, exc
                )
            else:
                self.logger.info("Updates refreshed for host %s", host.name)

        self.logger.info("Updates refreshed for all hosts")

    def run_all(
        self,
        host_method: str,
    ) -> Generator[tuple[Host, Any, Optional[Exception]]]:
        """
        Run a method on all hosts in the inventory.

        :param host_method: The method to run on each host
        :param log_msg_success: The log message to display on success.
        :param log_callback: Optional callback function to log results for each host.
                             Note that this overrides the value of log_msg_success

        """
        if not self.hosts:
            self.logger.warning("No hosts in inventory. Nothing to run.")
            yield from ()
            return

        # Sanity checks, these should only come in play if we have an internal
        # programming error, not a user error.

        # Ensure the host_method exists in the base class
        if not hasattr(Host, host_method):
            self.logger.error(
                "Host class does not have attribute '%s', refusing to execute!",
                host_method,
            )
            yield from ()
            return

        # Ensure the host_method is callable
        if not callable(getattr(Host, host_method)):
            self.logger.error(
                "Host class attribute '%s' is not callable, refusing to execute!",
                host_method,
            )
            yield from ()
            return

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(getattr(host, host_method)): host for host in self.hosts
            }

            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result()
                    self.logger.info(
                        "Successfully executed %s on %s", host_method, host.name
                    )
                    yield (host, result, None)
                except Exception as e:
                    self.logger.error(
                        "Failed to run %s on %s: %s", host_method, host.name, e
                    )
                    yield (host, None, e)
