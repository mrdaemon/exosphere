import inspect
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, StrEnum
from typing import Any, Generator, assert_never

from exosphere import migrations
from exosphere.config import Configuration
from exosphere.data import HostState
from exosphere.database import DiskCache
from exosphere.objects import Host


class FilterMode(StrEnum):
    """
    Filter modes for inventory views.

    Values are human-readable labels, suitable for display in both the
    CLI status output and the TUI inventory screen.
    """

    NONE = "All Hosts"
    UPDATES_ONLY = "Updates"
    SECURITY_ONLY = "Security Updates"


class SortField(Enum):
    """
    Sortable columns for inventory views.

    Each member carries everything needed to sort by it:

    - The column token (used as name for user input, e.g. "version")
    - The display ``label`` (used for display in table headers)
    - The ``key`` function, producing a sort key for a given Host
    - The ``has_value`` predicate, telling whether a host has a real,
      orderable value for this column (used to pin "no data" hosts to the
      bottom of the sort)

    Every key returns a tuple so the sort is total and undiscovered
    values land consistently. Because the sort is stable, hosts
    comparing as equal keep their existing relative order (i.e.
    configuration order).

    Sorting by ``version`` is compound (flavor first, then a natural
    sort of the version) since versions are not comparable across
    flavors. Likewise, sorting by ``flavor`` is compound by OS first
    so the OS families stay grouped together.
    """

    # Tuple is (token, label, sort key function, has_value predicate)
    HOST = ("host", "Host", lambda h: (h.name.lower(),), lambda h: True)
    OS = ("os", "OS", lambda h: SortField._text(h.os), lambda h: h.os is not None)
    FLAVOR = (
        "flavor",
        "Flavor",
        # Compound sort by OS first
        lambda h: (*SortField._text(h.os), *SortField._text(h.flavor)),
        lambda h: h.flavor is not None,
    )
    VERSION = (
        "version",
        "Version",
        # Compound sort by flavor first
        lambda h: (*SortField._text(h.flavor), SortField._version(h.version)),
        lambda h: h.version is not None,
    )
    UPDATES = (
        "updates",
        "Updates",
        lambda h: (len(h.updates),),
        lambda h: h.supported and h.os is not None,
    )
    SECURITY = (
        "security",
        "Security",
        lambda h: (len(h.security_updates),),
        lambda h: h.supported and h.os is not None,
    )
    # online first; status is known for every host
    STATUS = ("status", "Status", lambda h: (not h.online,), lambda h: True)

    # Annotations, not members
    label: str
    key: Callable[[Host], tuple]
    has_value: Callable[[Host], bool]

    def __new__(
        cls,
        token: str,
        label: str,
        key: Callable[[Host], tuple],
        has_value: Callable[[Host], bool],
    ) -> "SortField":
        member = object.__new__(cls)
        member._value_ = token
        member.label = label
        member.key = key
        member.has_value = has_value
        return member

    @staticmethod
    def _text(value: str | None) -> tuple:
        """Sort key for optional strings: present first, None/empty last."""
        return (value is None or value == "", (value or "").lower())

    @staticmethod
    def _version(value: str | None) -> tuple:
        """
        Natural-sort key for a version string; None/empty sorts last.

        Splits the version into numeric and non-numeric chunks so numeric
        segments compare as integers (9 < 12 < 22) rather than
        lexically. Each chunk is wrapped in a (type, value) tuple so
        numeric and string chunks never compare against each other.
        """
        if not value:
            # Sort undiscovered/unknown versions last
            return ((2,),)

        return tuple(
            (0, int(part)) if part.isdigit() else (1, part.lower())
            for part in re.findall(r"\d+|[^\d]+", value)
        )


class HostOperation(Enum):
    """
    Operations that can be dispatched against a Host.

    Each member's value is the name of a Host method, and doubles as
    the stable task identifier.

    The label value is a human-readable name for the operation,
    suitable for display.

    The modifies_state boolean indicates whether or not the operation
    modifies the host's state (e.g. by making change to HostData).
    If the operation does not (for instance, syncing repositories),
    this should be set to False.
    """

    # Tuple is (Host method name, display label, modifies local state)
    PING = ("ping", "Ping", True)
    DISCOVER = ("discover", "Discover", True)
    REFRESH = ("refresh_updates", "Refresh Updates", True)
    SYNC = ("sync_repos", "Sync Repositories", False)

    # Annotations, not members
    label: str
    modifies_state: bool

    def __new__(cls, method: str, label: str, modifies_state: bool) -> "HostOperation":
        member = object.__new__(cls)
        member._value_ = method
        member.label = label
        member.modifies_state = modifies_state
        return member


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
                cache[host.name] = host.to_state()

    def close_all(self, clear: bool = False) -> None:
        """
        Close all SSH connections for all hosts in the inventory.

        Invokes the `close` method on each Host object, closing the ssh
        connection if one exists.

        It will be re-established on next request.

        :param clear: If True, clears the connection object on each host
                      after closing it by setting it to None.

        """
        self.logger.debug("Closing all SSH connections for %d hosts", len(self.hosts))
        for host in self.hosts:
            host.close(clear=clear)

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

        self.logger.debug("Loading state from cache file %s", self.cache_file)
        self.logger.debug("Current Schema Version: %d", HostState.schema_version)

        # Load hosts state from cache if available
        with DiskCache(self.cache_file) as cache:
            for name, host in config_hosts.items():
                host_obj = self.load_or_create_host(name, host, cache)
                self.hosts.append(host_obj)
                cached_hosts.add(name)

            # If hosts are in cache but not in config, remove them
            if (
                self.configuration["options"]["cache_autopurge"]
                and self.configuration["options"]["cache_autosave"]
            ):
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

        host_obj: Host

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

        try:
            self.logger.debug("Loading host state for %s from cache", name)
            host_state: Host | HostState = cache[name]

            # Backwards compatibility, attempt to migrate full Host
            # objects to HostState if found in cache
            if isinstance(host_state, Host):
                host_state = migrations.migrate_from_host(host_state)

            self.logger.debug("Applying cached state to host %s", name)
            host_obj = Host(**host_cfg)
            host_obj.from_state(host_state)

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

    def filter_hosts(
        self, mode: FilterMode, hosts: list[Host] | None = None
    ) -> list[Host]:
        """
        Filter hosts by the given FilterMode.

        Operates on the provided list of hosts, or the entire inventory
        if none is given.

        Returns a new list of hosts matching the filter.

        :param mode: The FilterMode to apply
        :param hosts: Optional list of hosts to filter, defaults to
                      entire inventory
        :return: List of hosts matching the filter
        """
        target = hosts if hosts is not None else self.hosts

        match mode:
            case FilterMode.NONE:
                return list(target)
            case FilterMode.UPDATES_ONLY:
                return [h for h in target if h.supported and h.updates]
            case FilterMode.SECURITY_ONLY:
                return [h for h in target if h.supported and h.security_updates]
            case _:
                # Invalid filter mode
                # Reaching this implies a programming error
                assert_never(mode)

    def sort_hosts(
        self,
        by: SortField,
        hosts: list[Host] | None = None,
        reverse: bool = False,
    ) -> list[Host]:
        """
        Sort hosts by the given SortField.

        Operates on the provided list of hosts, or the entire inventory
        if none is given.

        The sort is stable, so hosts comparing equal retain their existing
        relative order (e.g. their order in the configuration file).

        Sorting by SortField.VERSION is compound: hosts are grouped by
        flavor first, then ordered by a natural-sort of their version
        within each flavor, since version strings are not meaningfully
        comparable across different flavors.

        Handling of hosts with placeholder/no data values is as follows

        - All hosts can always be sorted by name and online status,
          since those are always known
        - Undiscovered hosts have no platform data at all, so they sort
          last on every other data column
        - Unsupported hosts report an OS but nothing else, so they sort
          normally by OS but last on every other data column
        - Hosts with no data for a column are pinned to the bottom of
          the sort, regardless of desired order
        - Unsupported hosts sort after Undiscovered, since the latter
          are considered actionable.

        Returns a new list of hosts sorted by the given field.

        :param by: The SortField to sort by
        :param hosts: Optional list of hosts to sort; defaults to all
                      hosts in the inventory
        :param reverse: Whether to reverse the sort order
        :return: New list of hosts sorted by the given field
        """
        target = list(hosts if hosts is not None else self.hosts)

        # Pre-sort hosts into sets with and without values for column
        have_value = [h for h in target if by.has_value(h)]
        no_value = [h for h in target if not by.has_value(h)]

        # Undiscovered host sort above unsupported
        undiscovered = [h for h in no_value if h.supported]
        unsupported = [h for h in no_value if not h.supported]

        return (
            sorted(have_value, key=by.key, reverse=reverse) + undiscovered + unsupported
        )

    def discover_all(self) -> None:
        """
        Discover all hosts in the inventory.

        """
        self.logger.info("Discovering all hosts in inventory")

        for host, _, exc in self.run_task(
            HostOperation.DISCOVER,
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
            HostOperation.SYNC,
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
            HostOperation.REFRESH,
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
            HostOperation.PING,
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
        operation: HostOperation,
        hosts: list[Host] | None = None,
    ) -> Generator[tuple[Host, Any, Exception | None]]:
        """
        Run an operation on specified hosts in the inventory.
        If none are specified, run on all hosts.

        Uses a ThreadPoolExecutor to run the operation's Host method
        concurrently, and returns a generator that can be safely iterated
        over to process the results as the tasks complete.


        :param operation: The :class:`HostOperation` to run on each host
        :param hosts: Optional list of Host objects to run the operation on.
                      If unspecified, runs on all hosts in the inventory.

        :return: A generator yielding tuples of (host, result, exception)
        """

        method = operation.value
        target_hosts = hosts if hosts is not None else self.hosts

        self.logger.debug("Dispatching %s to %d host(s)", method, len(target_hosts))

        if not target_hosts:
            self.logger.warning("No hosts in inventory. Nothing to run.")
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
                method,
            )

            futures = {
                executor.submit(getattr(host, method)): host for host in target_hosts
            }

            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result()
                    self.logger.debug(
                        "Successfully executed %s on %s", method, host.name
                    )
                    yield (host, result, None)
                except Exception as e:
                    self.logger.error(
                        "Failed to run %s on %s: %s", method, host.name, e
                    )
                    yield (host, None, e)
