import logging
from datetime import datetime
from typing import Optional

from fabric import Connection

from exosphere import app_config
from exosphere.data import HostInfo, Update
from exosphere.errors import DataRefreshError, OfflineHostError
from exosphere.providers import PkgManagerFactory
from exosphere.providers.api import PkgManager
from exosphere.setup import detect


class Host:
    def __init__(self, name: str, ip: str, port: int = 22) -> None:
        """
        Create a Host object, which then can be used to query
        the host for information, and perform operations on it.

        The host will be marked at offline until the first sync
        operation is performed. Errors in processing will update
        this status automatically.

        :param name: Name of the host
        :param ip: IP address or FQDN of the host
        :param port: Port number for SSH connection (default is 22)
        """
        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Unpacked host information, usually from inventory
        self.name = name
        self.ip = ip
        self.port = port

        # Shared connection object
        self._connection: Optional[Connection] = None

        # online status, defaults to False
        # until first sync.
        self.online: bool = False

        # Internal state of host
        self.os: Optional[str] = None
        self.version: Optional[str] = None
        self.flavor: Optional[str] = None
        self.package_manager: Optional[str] = None

        # Package manager implementation
        self._pkginst: Optional[PkgManager] = None

        # Update Catalog for host
        self.updates: list[Update] = []

        # Timestamp of the last refresh operation
        # We store the datetime object straight up for convenience.
        self.last_refresh: Optional[datetime] = None

    def __getstate__(self) -> dict:
        """
        Custom getstate method to avoid serializing unserializables.
        Copies the state dict and plucks out stuff that doesn't
        serialize well, or is otherwise problematic.
        """
        state = self.__dict__.copy()
        state["_connection"] = None  # Do not serialize the connection
        state["_pkginst"] = None  # Do not serialize the package manager instance
        return state

    def __setstate__(self, state: dict) -> None:
        """
        Custom setstate method to restore the state of the object.
        Resets properties and members that are not serializable
        """
        self.__dict__.update(state)
        self._connection = None
        if "package_manager" in state:
            self._pkginst = PkgManagerFactory.create(state["package_manager"])

    @property
    def connection(self) -> Connection:
        """
        Establish a connection to the host using Fabric.
        This method sets up the connection object for further operations.

        Connection objects are recycled if already created.
        As a general rule, the connection should be closed, but this should
        be handled by the callee this gets passed on, as code is decoupled
        from the Host object for most operations.

        :return: Fabric Connection object
        :raises ConnectionError: If the connection cannot be established
        """
        if self._connection is None:
            logging.debug(
                "Creating new connection to %s at %s:%s",
                self.name,
                self.ip,
                self.port,
            )
            self._connection = Connection(host=self.ip, port=self.port)

        return self._connection

    @property
    def security_updates(self) -> list[Update]:
        """
        Get a list of security updates available on the host.

        :return: List of security updates
        """
        return [update for update in self.updates if update.security]

    @property
    def is_stale(self) -> bool:
        """
        Returns True if the hosts updates status is stale

        A host is considered stale if it has not been refreshed
        within the "stale_treshold" value in seconds set in the
        configuration. Default is 86400 seconds (24 hours).

        :return: True if the host is stale, False otherwise
        """
        if self.last_refresh is None:
            return True

        stale_threshold = app_config["options"]["stale_threshold"]
        timedelta = datetime.now() - self.last_refresh

        return timedelta.total_seconds() > stale_threshold

    def sync(self) -> None:
        """
        Synchronize host information with remote system.
        Effectively refreshes cache for host information.

        :return: None
        """

        # Check if the host is reachable before attempting anything else
        # This also updates the online status
        if not self.ping():
            self.logger.warning("Host %s is offline, skipping sync.", self.name)
            return

        try:
            platform_info: HostInfo = detect.platform_detect(self.connection)
        except OfflineHostError as e:
            self.logger.warning(
                "Host %s has gone offline during sync, received: %s",
                self.name,
                e,
            )
            self.online = False
            return
        except DataRefreshError as e:
            self.logger.error(
                "An error occurred during sync for %s: %s",
                self.name,
                e.stderr,
            )
            self.online = False
            raise DataRefreshError(
                f"An error occured during sync for {self.name}: {e}"
            ) from e

        self.os = platform_info.os
        self.version = platform_info.version
        self.flavor = platform_info.flavor
        self.package_manager = platform_info.package_manager

        self._pkginst = PkgManagerFactory.create(self.package_manager)
        self.logger.debug(
            "Using concrete package manager %s.%s for %s",
            self._pkginst.__class__.__module__,
            self._pkginst.__class__.__qualname__,
            self.package_manager,
        )

    def refresh_catalog(self) -> None:
        """
        Refresh the package catalog on the host.
        This is a placeholder for actual implementation.

        I'm still debating whether or not this should be a pluggable
        system with a generic Package Manager interface, as what we
        want to do here is very simple, and almost read-only.

        TODO: Implement a generic package manager interface

        :return: None
        """
        if not self.online:
            raise OfflineHostError(f"Host {self.name} is offline.")

        if self._pkginst is None:
            self.logger.warning(
                "Platform data missing! Forcing sync, "
                "but this indicates an ordering bug."
            )
            self.sync()

        if self._pkginst is not None:
            pkg_manager = self._pkginst
            if not pkg_manager.reposync(self.connection):
                raise DataRefreshError(
                    f"Failed to refresh package catalog on {self.name}"
                )

    def refresh_updates(self) -> None:
        """
        Refresh the list of available updates on the host.
        This method retrieves the list of available updates and
        populates the `updates` attribute.

        :return: None
        """
        if not self.online:
            raise OfflineHostError(f"Host {self.name} is offline.")

        if self._pkginst is not None:
            pkg_manager = self._pkginst
            self.updates = pkg_manager.get_updates(self.connection)
        else:
            self.logger.error(
                "Package manager implementation unavailable, "
                "this is likely due to sync failure."
            )
            raise DataRefreshError(
                f"Failed to refresh updates on {self.name}: "
                "No package manager implementation could be used."
            )

        if not self.updates:
            self.logger.info("No updates available for %s", self.name)
        else:
            self.logger.info(
                "Found %d updates for %s: %s",
                len(self.updates),
                self.name,
                ", ".join(str(update) for update in self.updates),
            )

        # Update the last refresh timestamp
        self.last_refresh = datetime.now()

    def ping(self) -> bool:
        """
        Check if the host is reachable.

        :return: True if the host is reachable, False otherwise
        """
        try:
            self.logger.debug("Pinging host %s at %s:%s", self.name, self.ip, self.port)
            self.connection.run("echo 'ping'", hide=True)
            self.online = True
        except Exception as e:
            self.logger.error("Ping to host %s failed: %s", self.name, e)
            self.online = False
        finally:
            self.connection.close()
            return self.online

    def __str__(self):
        return (
            f"{self.name} ({self.ip}:{self.port}) "
            f"[{self.os}, {self.version}, {self.flavor}, "
            f"{self.package_manager}], {'Online' if self.online else 'Offline'}"
        )

    def __repr__(self):
        return f"Host(name='{self.name}', ip='{self.ip}', port='{self.port}')"
