import inspect
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator

from exosphere import app_config
from exosphere.config import Configuration
from exosphere.database import DiskCache
from exosphere.objects import Host
from exosphere.security import SudoPolicy


class Inventory:
    """
    Inventory and state management

    Handles reading the inventory from file and creating the
    Host objects.

    Also handles dispatching tasks to the Host objects, via a parallelized
    ThreadPoolExecutor.

    Convenience methods for discovery, repo sync, updates refresh and ping
    are provided, and are all parallelized using Threads.

    Runtime errors are generally non-fatal, but will be logged.
    The Host objects themselves usually handle their own failure cases
    and will log errors as appropriate, on top of flagging themselves
    as offline if they are unable to perform their tasks.
    """

    def __init__(self, config: Configuration) -> None:
        """
        Initialize the Inventory object with default values.

        :param config: The configuration object containing the inventory
        """
        self.configuration = config
        self.cache_file = config["options"]["cache_file"]

        self.hosts: list[Host] = []

        self.logger = logging.getLogger(__name__)

        # Populate inventory from configuration on init
        self.init_all()

    def save_state(self) -> None:
        """
        Save the current state of inventory hosts to the cache file.
        """
        with DiskCache(self.cache_file) as cache:
            self.logger.info("Saving inventory state to cache file %s", self.cache_file)
            for host in self.hosts:
                cache[host.name] = host

    def clear_state(self) -> None:
        """
        Clear the current state of the inventory
        This will remove the cache file and re-init the inventory.
        """
        self.logger.info("Clearing inventory state")
        try:
            with DiskCache(self.cache_file) as cache:
                cache.clear()
        except FileNotFoundError:
            self.logger.warning(
                "Cache file %s not found, nothing to clear", self.cache_file
            )
        except Exception as e:
            self.logger.error("Failed to clear cache file: %s", str(e))
            raise RuntimeError(
                f"Failed to clear cache file {self.cache_file}: {str(e)}"
            ) from e

        # Re-initialize the inventory
        self.init_all()

    def init_all(self) -> None:
        """
        Setup the inventory by creating Host objects from the
        configuration.

        Existing state will be cleared in the process.
        """
        self.hosts: list[Host] = []

        if len(self.configuration["hosts"]) == 0:
            self.logger.warning("No hosts found in inventory")
            # While we COULD purge the cache here, ALL hosts being gone
            # feels like a transient mistake, so we err on the side of
            # caution and just leave it as is.
            return

        config_hosts = {host["name"]: host for host in self.configuration["hosts"]}
        cached_hosts = set()

        self.logger.debug(
            "Initializing inventory with %d hosts", len(self.configuration["hosts"])
        )

        # Load hosts state from cache if available
        with DiskCache(self.cache_file) as cache:
            for name, host in config_hosts.items():
                host_obj = self.load_or_create_host(name, host, cache)
                self.hosts.append(host_obj)
                cached_hosts.add(name)

            # If hosts are in cache but not in config, remove them
            if self.configuration["options"].get("cache_autopurge"):
                for host in list(cache.keys()):
                    if host not in cached_hosts:
                        self.logger.info("Removing stale host %s from cache", host)
                        del cache[host]

    def load_or_create_host(
        self, name: str, host_cfg: dict[str, Any], cache: DiskCache
    ) -> Host:
        """
        Attempt to load a host from the cache, or create a new one if that fails
        in any meaningful way.

        Is also responsible for binding the host configuration parameters
        to the Host object ones, and will log a warning if invalid parameters
        are found in the configuration dictionary.

        Invalid parameters will be ignored.

        The new host's other configuration properties will be updated
        if they have changed from config since (i.e. ip address, port etc)

        :param name: The name of the host to load or create
        :param host_cfg: The configuration dictionary for the host
        :param cache: The DiskCache instance to use for loading the host
        :return: An instance of Host
        """

        # Validate the host configuration, remove entries that are not
        # parameters to the Host class constructor with a warning
        valid_params = {
            k for k in inspect.signature(Host.__init__).parameters.keys() if k != "self"
        }
        for key in list(host_cfg.keys()):
            if key not in valid_params:
                self.logger.warning(
                    "Invalid host configuration option '%s' for host '%s', ignoring.",
                    key,
                    name,
                )
                del host_cfg[key]

        # Return early on cache miss
        if name not in cache:
            self.logger.debug("Host %s not found in cache, creating new", name)
            return Host(**host_cfg)

        def reset_property(host_obj: Host, attr_name: str, default_value: Any) -> None:
            if getattr(host_obj, attr_name) != default_value:
                self.logger.debug(
                    "Resetting %s on host %s as it is no longer in config",
                    attr_name,
                    name,
                )
                setattr(host_obj, attr_name, default_value)

        try:
            self.logger.debug("Loading host state for %s from cache", name)
            host_obj = cache[name]

            # Update host properties with configuration values
            for k, v in host_cfg.items():
                if k == "name":
                    continue
                setattr(host_obj, k, v)

            # Return properties to defaults if they are not in config
            port_default = inspect.signature(Host.__init__).parameters["port"].default
            connect_timeout_default = int(app_config["options"]["default_timeout"])
            sudo_policy_default = SudoPolicy(
                app_config["options"]["default_sudo_policy"].lower()
            )

            if "port" not in host_cfg:
                reset_property(host_obj, "port", port_default)

            if "connect_timeout" not in host_cfg:
                reset_property(host_obj, "connect_timeout", connect_timeout_default)

            if "sudo_policy" not in host_cfg:
                reset_property(host_obj, "sudo_policy", sudo_policy_default)

            # Also remove optional properties that are no longer in config
            # by resetting them to None
            for k in Host.OPTIONAL_PARAMS:
                if k not in host_cfg:
                    reset_property(host_obj, k, None)

        except Exception as e:
            self.logger.warning(
                "Failed to load host state for %s from cache: %s, recreating anew.",
                name,
                str(e),
            )
            host_obj = Host(**host_cfg)

        return host_obj

    def get_host(self, name: str) -> Host | None:
        """
        Get a Host object by name from the inventory

        If the host is not found, it returns None and logs an error message.
        If the inventory was properly loaded, there a unicity constraint on
        host names, so you can reasonably expect to not have to deal with
        duplicates.

        :param name: The name of the host to retrieve, e.g. "webserver1"
        :return: The Host object if found, None otherwise
        """

        host = next((h for h in self.hosts if h.name == name), None)

        if host is None:
            self.logger.error("Host '%s' not found in inventory", name)
            return None

        return host

    def discover_all(self) -> None:
        """
        Discover all hosts in the inventory.

        """
        self.logger.info("Discovering all hosts in inventory")

        for host, _, exc in self.run_task(
            "discover",
        ):
            if exc:
                self.logger.error("Failed to discover host %s: %s", host.name, exc)
            else:
                self.logger.info("Host %s discovered successfully", host.name)

        self.logger.info("All hosts discovered")

    def sync_repos_all(self) -> None:
        """
        Sync the package repositories on all hosts in the inventory.

        This method will call the `sync_repos` method on each
        Host object in the inventory.
        """
        self.logger.info("Syncing repositories for all hosts")

        for host, _, exc in self.run_task(
            "sync_repos",
        ):
            if exc:
                self.logger.error(
                    "Failed to sync repositories for host %s: %s", host.name, exc
                )
            else:
                self.logger.info("Package repositories synced for host %s", host.name)

        self.logger.info("Package repositories synced for all hosts")

    def refresh_updates_all(self) -> None:
        """
        Refresh the list of available updates on all hosts in the inventory.

        This method will call the `refresh_updates` method on each
        Host object in the inventory.
        """

        self.logger.info("Refreshing updates for all hosts")

        for host, _, exc in self.run_task(
            "refresh_updates",
        ):
            if exc:
                self.logger.error(
                    "Failed to refresh updates for host %s: %s", host.name, exc
                )
            else:
                self.logger.info("Updates refreshed for host %s", host.name)

        self.logger.info("Updates refreshed for all hosts")

    def ping_all(self) -> None:
        """
        Ping all hosts in the inventory.

        This method will call the `ping` method on each Host object
        in the inventory and log whether each host is online or offline.
        """
        self.logger.info("Pinging all hosts in inventory")

        for host, online, exc in self.run_task(
            "ping",
        ):
            if exc:
                # This should not happen since "ping" does not raise exceptions.
                # We're still going to catch and log it if it ever does.
                self.logger.error("Failed to ping host %s: %s", host.name, exc)
            else:
                status = "offline" if not online else "online"
                self.logger.info("Host %s is %s", host.name, status)

        self.logger.info("Pinged all hosts")

    def run_task(
        self,
        host_method: str,
        hosts: list[Host] | None = None,
    ) -> Generator[tuple[Host, Any, Exception | None]]:
        """
        Run a method on specified hosts in the inventory.
        If none are specified, run on all hosts.

        Uses a ThreadPoolExecutor to run the provided method concurrently,
        and returns a generator that can be safely iterated over to process
        the results as the tasks complete.

        :param host_method: The method to run on each host
        :param hosts: Optional list of Host objects to run the method on.
                      If unspecified, runs on all hosts in the inventory.

        :return: A generator yielding tuples of (host, result, exception)
        """

        target_hosts = hosts if hosts is not None else self.hosts

        self.logger.debug(
            "Dispatching %s to %d host(s)", host_method, len(target_hosts)
        )

        if not target_hosts:
            self.logger.warning("No hosts in inventory. Nothing to run.")
            yield from ()
            return

        # Sanity checks, these should only come in play if we have an internal
        # programming error, not a user error.
        #
        # TODO: I honestly feel these checks could be removed entirely.
        #       It is better to just let the returned exc field contain the
        #       error and treat it like any other issue, but I'm leaving them
        #       in since this can be difficult to debug in context.

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

        with ThreadPoolExecutor(
            max_workers=self.configuration["options"]["max_threads"]
        ) as executor:
            self.logger.debug(
                "Using ThreadPoolExecutor with %d threads",
                self.configuration["options"]["max_threads"],
            )
            self.logger.debug(
                "Submitting %d tasks to executor for method '%s'",
                len(target_hosts),
                host_method,
            )

            futures = {
                executor.submit(getattr(host, host_method)): host
                for host in target_hosts
            }

            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result()
                    self.logger.debug(
                        "Successfully executed %s on %s", host_method, host.name
                    )
                    yield (host, result, None)
                except Exception as e:
                    self.logger.error(
                        "Failed to run %s on %s: %s", host_method, host.name, e
                    )
                    yield (host, None, e)
