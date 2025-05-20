import logging
from typing import Optional

from fabric import Connection

from exosphere.data import HostInfo, Update
from exosphere.errors import DataRefreshError, OfflineHostError
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

        # Update Catalog for host
        self.updates: list[Update] = []

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
                e,
            )
            self.online = False
            raise DataRefreshError(
                f"An error occured during sync for {self.name}: {e}"
            ) from e

        self.os = platform_info.os
        self.version = platform_info.version
        self.flavor = platform_info.flavor
        self.package_manager = platform_info.package_manager

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

        raise NotImplementedError("refresh_catalog method is not implemented.")

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
        return f"Host({self.name}, {self.ip}, {self.port})"
