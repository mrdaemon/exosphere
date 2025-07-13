import inspect
import logging
from datetime import datetime

from fabric import Connection

from exosphere import app_config
from exosphere.data import HostInfo, Update
from exosphere.errors import DataRefreshError, OfflineHostError
from exosphere.providers import PkgManagerFactory
from exosphere.providers.api import PkgManager
from exosphere.setup import detect


class Host:
    """
    Host object representing a remote system.

    This object can be used to query the host for information,
    perform operations on it as well as manage its state.

    The host will be marked as offline until the first discovery
    operation is performed. Errors in processing will update
    this status automatically.

    """

    # Serialization hint for optional parameters
    # of this class that can safely be set to None
    # if they are missing from the serialized state.
    OPTIONAL_PARAMS = [
        "username",
        "description",
    ]

    def __init__(
        self,
        name: str,
        ip: str,
        port: int = 22,
        username: str | None = None,
        description: str | None = None,
        connect_timeout: int | None = None,
    ) -> None:
        """
        Create a new Host Object

        Note: The paramaters of the Host object can and will be
        affected by the process of reloading them from cache!
        See: `exosphere.inventory.Inventory.load_or_create_host`

        Keep in mind the need to verify this process if you make
        changes to the constructor signature or default values.

        Intended to be serializable!

        :param name: Name of the host
        :param ip: IP address or FQDN of the host
        :param port: Port number for SSH connection (default is 22)
        :param username: SSH username (optional, will use current if not provided)
        :param description: Optional description for the host
        :param connect_timeout: Connection timeout in seconds (optional)
        """
        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Unpacked host information, usually from inventory
        self.name = name
        self.ip = ip
        self.port = port
        self.description = description

        # SSH username, if provided
        self.username: str | None = username

        # Shared connection object
        self._connection: Connection | None = None

        # Connection timeout - if not set per-host, will use the
        # default timeout from the configuration.
        self.connect_timeout: int = (
            connect_timeout or app_config["options"]["default_timeout"]
        )

        # online status, defaults to False
        # until first discovery.
        self.online: bool = False

        # Internal state of host
        self.os: str | None = None
        self.version: str | None = None
        self.flavor: str | None = None
        self.package_manager: str | None = None

        # Package manager implementation
        self._pkginst: PkgManager | None = None

        # Update Catalog for host
        self.updates: list[Update] = []

        # Timestamp of the last refresh operation
        # We store the datetime object straight up for convenience.
        self.last_refresh: datetime | None = None

    def __getstate__(self) -> dict:
        """
        Custom getstate method to avoid serializing unserializables.
        Copies the state dict and plucks out stuff that doesn't
        serialize well, or is otherwise problematic.
        """
        state = self.__dict__.copy()
        state["_connection"] = None  # Do not serialize the connection
        state["_pkginst"] = None  # Do not serialize the package manager instance
        state["logger"] = None  # Do not serialize the logger
        return state

    def __setstate__(self, state: dict) -> None:
        """
        Custom setstate method to restore the state of the object.
        Resets properties and members that are not serializable

        Additionally, ensures that all parameters with defaults
        are properly set, to avoid issues during deserialization
        between different versions of the Host class.
        """

        self.__dict__.update(state)

        # Reset unserializables
        self.logger = logging.getLogger(__name__)
        self._connection = None
        if "package_manager" in state:
            self._pkginst = PkgManagerFactory.create(state["package_manager"])

        # Ensure all parameters with defaults are properly set
        # This helps during version/signature changes.
        signature = inspect.signature(self.__init__)

        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if not hasattr(self, name):
                if param.default is not inspect.Parameter.empty:
                    setattr(self, name, param.default)
                else:
                    raise ValueError(
                        "Unable to de-serialize Host object state: "
                        f"Missing required parameter '{name}' in Host object state"
                    )

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
            conn_args = {
                "host": self.ip,
                "port": self.port,
                "connect_timeout": self.connect_timeout,
            }

            # Determine which username to use for the connection.
            # In the absence of either a provided or global default username,
            # Fabric will use the current system user, as you would expect.
            user_param: str | None = None
            if self.username:
                user_param = self.username
                self.logger.debug(
                    "Using provided username '%s' for connection to %s",
                    self.username,
                    self.name,
                )
            elif app_config["options"]["default_username"]:
                # Use the default global username if set
                user_param = app_config["options"]["default_username"]
                self.logger.debug(
                    "Using default global username '%s' for connection to %s",
                    app_config["options"]["default_username"],
                    self.name,
                )

            if user_param:
                conn_args["user"] = user_param

            conn_string = (
                f"{user_param}@{self.ip}:{self.port}"
                if user_param
                else f"{self.ip}:{self.port}"
            )

            self.logger.debug(
                "Creating new connection to %s using %s, (timeout: %s)",
                self.name,
                conn_string,
                self.connect_timeout,
            )
            self._connection = Connection(**conn_args)

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
        Check if the host is staled based on refresh timestamp

        A host is considered stale if it has not been refreshed
        within the "stale_threshold" value in seconds set in the
        configuration. Default is 86400 seconds (24 hours).

        :return: True if the host is stale, False otherwise
        """
        if self.last_refresh is None:
            return True

        stale_threshold = app_config["options"]["stale_threshold"]
        timedelta = datetime.now() - self.last_refresh

        return timedelta.total_seconds() > stale_threshold

    def discover(self) -> None:
        """
        Synchronize host information with remote system.
        Attempts to detect the platform details, such as
        operating system, version, flavor, and package manager.

        Online status is also updated in the process.
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
                str(e),
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
                f"An error occured during sync for {self.name}: {str(e)}"
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

        Will invoke the concrete package manager provider implementation
        associated during initial host sync.

        This is the equivalent of your 'apt-get update' or similar

        """
        if not self.online:
            raise OfflineHostError(f"Host {self.name} is offline or unreachable.")

        # If the concrete package manager provider is not set,
        # refuse the temptation to guess or force a sync, and throw
        # an exception instead. Caller can deal with it.
        if self._pkginst is None:
            self.logger.error(
                "Package manager implementation unavailable, "
                "this is likely due to sync failure."
            )
            raise DataRefreshError(
                f"Failed to refresh updates on {self.name}: "
                "No package manager implementation could be used."
            )

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
                "Found %d updates for %s",
                len(self.updates),
                self.name,
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
