import logging
import time
from datetime import datetime, timezone
from threading import RLock
from typing import TypeAlias

from fabric import Connection
from paramiko.ssh_exception import PasswordRequiredException

from exosphere import app_config
from exosphere.data import HostInfo, HostState, Update
from exosphere.errors import (
    AUTH_FAILURE_MESSAGE,
    DataRefreshError,
    OfflineHostError,
    UnsupportedOSError,
)
from exosphere.providers import PkgManagerFactory
from exosphere.providers.api import PkgManager
from exosphere.security import SudoPolicy, check_sudo_policy
from exosphere.setup import detect

# Define a type alias for timezone-aware UTC datetime
# This is to help communicate intent better in type hints
UtcDateTime: TypeAlias = datetime


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
        sudo_policy: str | None = None,
    ) -> None:
        """
        Create a new Host Object

        Note: The parameters of the Host object can and will be
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
        :param sudo_policy: Sudo policy for package manager operations (skip, nopasswd)
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

        # Last use of shared connection
        self._connection_last_used: float | None = None

        # Lock for thread-safe access to connection state
        self._connection_state_lock = RLock()

        # Connection timeout - if not set per-host, will use the
        # default timeout from the configuration.
        self.connect_timeout: int = (
            connect_timeout or app_config["options"]["default_timeout"]
        )

        # Sudo Policy for package manager operations
        target_policy: str = sudo_policy or app_config["options"]["default_sudo_policy"]
        self.sudo_policy: SudoPolicy = SudoPolicy(target_policy.lower())

        # online status, defaults to False
        # until first discovery.
        self.online: bool = False

        # Default supported state is true
        # All hosts are assumed supported until
        # discover reports otherwise.
        self.supported: bool = True

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
        # This should be a timezone-aware UTC datetime!
        self.last_refresh: UtcDateTime | None = None

    def from_state(self, state: HostState) -> None:
        """
        Update the Host object from a HostState dataclass instance.
        Useful for loading state from disk or cache.

        :param state: HostState instance to load state from
        """

        # Warn in case of schema version mismatch
        if state.schema_version > HostState.schema_version:
            self.logger.warning(
                "HostState schema version %d is newer! (expected %d.) "
                "This may indicate a cache from a newer version and may cause issues.",
                state.schema_version,
                HostState.schema_version,
            )

        # V1 state mapping
        self.os = state.os
        self.version = state.version
        self.flavor = state.flavor
        self.package_manager = state.package_manager
        self.supported = state.supported
        self.online = state.online
        self.updates = list(state.updates)
        self.last_refresh = state.last_refresh

        # NOTE: For future schema versions involving simple new fields,
        # a simple check for state.schema_version to skip loading those
        # should be sufficient to let the class defaults take over.
        # Anything more involved should invoke migration logic in the
        # migrations module, and implemented in load_or_create_host.
        # See the inventory module for details.

        # Instantiate concrete package manager if defined
        if self.package_manager and self.supported:
            self._pkginst = PkgManagerFactory.create(self.package_manager)
        else:
            self._pkginst = None

    def to_state(self) -> HostState:
        """
        Convert the Host object to a HostState dataclass instance.
        Useful for serialization to disk or caching.

        :return: HostState instance representing the current state of the Host
        """
        return HostState(
            os=self.os,
            version=self.version,
            flavor=self.flavor,
            package_manager=self.package_manager,
            supported=self.supported,
            online=self.online,
            updates=tuple(self.updates),
            last_refresh=self.last_refresh,
        )

    def to_dict(self) -> dict:
        """
        Convert the Host object to a dictionary representation.
        Useful for serialization or reporting

        Note: Only includes informational fields, does not include
        configuration or connection details.

        Any datetime fields are represented as ISO 8601 strings in UTC.
        They explicitly follow what JavaScript's Date.toJSON() produces
        for maximum compatibility.

        :return: Dictionary representation of the Host object
        """
        return {
            "name": self.name,
            "description": self.description,
            "ip": self.ip,
            "port": self.port,
            "os": self.os,
            "flavor": self.flavor,
            "version": self.version,
            "supported": self.supported,
            "online": self.online,
            "package_manager": self.package_manager,
            "updates": [update.__dict__.copy() for update in self.updates],
            "last_refresh": self.last_refresh.isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")
            if self.last_refresh
            else None,
        }

    @property
    def connection(self) -> Connection:
        """
        Establish a connection to the host using Fabric.
        This method sets up the connection object for further operations.

        Connection objects are recycled if already created.

        If you work with Host objects directly, make sure to call
        `host.close()` when done with operations (such as discover,
        refresh_updates, etc) to avoid leaving ssh connections open.

        If you don't, all connections will be closed automatically on
        program exit.

        :return: Fabric Connection object
        """
        # Acquire lock mostly for thread-safety of our own attributes.
        # Fabric's Connection object is thread-safe in itself.
        with self._connection_state_lock:
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

            # Update last used timestamp on each access
            self._connection_last_used = time.time()

            return self._connection

    @property
    def connection_last_used(self) -> float | None:
        """
        Get the timestamp of the last use of the connection.

        "last used" here is defined as the last time anything requested
        the `Connection` object through the property for this host.

        Property access is thread-safe, and will reset the timestamp
        to None if the connection is no longer active.

        :return: Timestamp of last use in seconds since epoch, or None
                 if connection has never been used.
        """
        with self._connection_state_lock:
            if not self.is_connected and self._connection_last_used is not None:
                self.logger.warning(
                    "Connection to %s no longer active, resetting last used", self.name
                )
                self._connection_last_used = None
                return None

            return self._connection_last_used

    @property
    def is_connected(self) -> bool:
        """
        Check if the host has an active SSH connection.

        :return: True if connection exists and is connected, False otherwise
        """
        return self._connection is not None and self._connection.is_connected

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
        # Unsupported hosts cannot be stale by definition
        if not self.supported:
            return False

        if self.last_refresh is None:
            return True

        stale_threshold = app_config["options"]["stale_threshold"]
        timedelta = datetime.now(timezone.utc) - self.last_refresh

        return timedelta.total_seconds() > stale_threshold

    def discover(self) -> None:
        """
        Synchronize host information with remote system.
        Attempts to detect the platform details, such as
        operating system, version, flavor, and package manager.

        Online status is also updated in the process.
        """

        # Try ping first for auth/connectivity validation
        ping_failed = False
        ping_exception = None
        try:
            self.ping(raise_on_error=True, close_connection=False)
        except OfflineHostError as e:
            ping_failed = True
            ping_exception = e
            self.logger.debug(
                "Ping failed, will attempt platform detection for better error diagnosis"
            )

        try:
            platform_info: HostInfo = detect.platform_detect(self.connection)
            # Handle the rare case where we'd get here with a ping issue
            if ping_failed:
                self.logger.warning(
                    "Ping failed but platform detection succeeded for host %s",
                    self.name,
                )
                self.online = True
        except OfflineHostError as e:
            # If both ping and platform detection failed, prefer the ping error
            # since it likely has better auth/connectivity failure details.
            if ping_failed and ping_exception:
                self.logger.warning("Host %s is offline, skipping discover.", self.name)
                raise ping_exception
            else:
                self.logger.warning(
                    "Host %s has gone offline during sync, received: %s",
                    self.name,
                    str(e),
                )
                self.online = False
                raise
        except UnsupportedOSError:
            # This is the real issue - more useful than any ping failure
            self.logger.error(
                "Host %s is running a completely unsupported OS.",
                self.name,
            )
            # Don't mark as Online in this case
            self.online = False
            raise
        except DataRefreshError as e:
            # Prefer the ping error here as well, if available
            if ping_failed and ping_exception:
                self.logger.warning("Host %s is offline, skipping discover.", self.name)
                raise ping_exception
            else:
                self.logger.debug(
                    "An error occurred during discover for %s: %s",
                    self.name,
                    e.stderr,
                )
                self.online = False
                raise
        finally:
            if not app_config["options"]["ssh_pipelining"]:
                self.close()

        # Update host info based on detection results
        self.os = platform_info.os
        self.supported = platform_info.is_supported

        # In case of unsupported platform, return OS name only
        if not platform_info.is_supported:
            self.logger.info(
                "Host %s is online but uses an unsupported OS/platform: %s",
                self.name,
                platform_info.os,
            )
            self.version = None
            self.flavor = None
            self.package_manager = None
            self._pkginst = None
            return

        self.version = platform_info.version
        self.flavor = platform_info.flavor
        self.package_manager = platform_info.package_manager

        if self.package_manager:
            self._pkginst = PkgManagerFactory.create(self.package_manager)
            self.logger.debug(
                "Using concrete package manager %s.%s for %s",
                self._pkginst.__class__.__module__,
                self._pkginst.__class__.__qualname__,
                self.package_manager,
            )
        else:
            self.logger.error(
                "Supported platform without a package manager!"
                " This is likely a bug, and should be reported."
            )
            self._pkginst = None

    def sync_repos(self) -> None:
        """
        Sync the package repositories on the host.

        Will invoke the concrete package manager provider implementation
        associated during initial host sync.

        This is the equivalent of your 'apt-get update' or similar

        """
        if not self.online:
            raise OfflineHostError(f"Host {self.name} is offline or unreachable.")

        # If the platform is not supported, skip operation
        if not self.supported:
            self.logger.warning(
                "Host %s uses an unsupported OS/platform. "
                "Repository sync is not available.",
                self.name,
            )
            return

        # If the concrete package manager provider is not set,
        # refuse the temptation to guess or force a sync, and throw
        # an exception instead. Caller can deal with it.
        if self._pkginst is None:
            self.logger.error("Package manager implementation unavailable!")
            raise DataRefreshError(
                f"Failed to refresh updates on {self.name}: "
                "No package manager implementation could be used."
            )

        # Check if we can run this with the current SudoPolicy
        if not check_sudo_policy(self._pkginst.reposync, self.sudo_policy):
            self.logger.warning(
                "Skipping package repository sync on %s due to SudoPolicy: %s",
                self.name,
                self.sudo_policy,
            )
            return

        try:
            pkg_manager = self._pkginst
            if not pkg_manager.reposync(self.connection):
                raise DataRefreshError(
                    f"Failed to sync package repositories on {self.name}"
                )
        finally:
            # Close connection if pipelining is disabled
            if not app_config["options"]["ssh_pipelining"]:
                self.close()

    def refresh_updates(self) -> None:
        """
        Refresh the list of available updates on the host.
        This method retrieves the list of available updates and
        populates the `updates` attribute.

        """
        if not self.online:
            raise OfflineHostError(f"Host {self.name} is offline.")

        # If the platform is not supported, skip operation
        if not self.supported:
            self.logger.warning(
                "Host %s uses an unsupported OS/platform. "
                "Update refresh is not available.",
                self.name,
            )
            return

        if self._pkginst is None:
            self.logger.error("Package manager implementation unavailable!")
            raise DataRefreshError(
                f"Failed to refresh updates on {self.name}: "
                "No package manager implementation could be used."
            )

        # Check if we can run this with the current SudoPolicy
        if not check_sudo_policy(self._pkginst.get_updates, self.sudo_policy):
            self.logger.warning(
                "Skipping updates refresh on %s due to SudoPolicy: %s",
                self.name,
                self.sudo_policy,
            )
            return

        try:
            pkg_manager = self._pkginst
            self.updates = pkg_manager.get_updates(self.connection)
        finally:
            if not app_config["options"]["ssh_pipelining"]:
                self.close()

        if not self.updates:
            self.logger.info("No updates available for %s", self.name)
        else:
            self.logger.info(
                "Found %d updates for %s",
                len(self.updates),
                self.name,
            )

        # Update the last refresh timestamp
        self.last_refresh = datetime.now(timezone.utc)

    def close(self, clear: bool = False) -> None:
        """
        Close the SSH connection if one exists.

        Explicitly close the Connection object.
        Subsequent calls to `connection` property will recreate it if
        necessary.

        This should be called when done with batch operations on the
        host or when cleaning up on exit.

        You can use the `clear` parameter to also clear the internal
        connection object after closing it, if you want to ensure
        it is not reused.

        :param clear: If True, sets the internal connection object
                      to None after closing.
        """
        # Acquire lock for thread-safe access to our own attributes
        with self._connection_state_lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                    self.logger.debug(
                        "Closed SSH connection to %s (%s:%s)",
                        self.name,
                        self.ip,
                        self.port,
                    )
                except Exception as e:
                    # Errors here are non-fatal, just log them
                    self.logger.warning(
                        "Error closing connection to %s: %s", self.name, e
                    )
                finally:
                    self._connection_last_used = None

                    if clear:
                        self.logger.debug(
                            "Clearing connection object for host %s", self.name
                        )
                        self._connection = None

    def ping(self, raise_on_error: bool = False, close_connection: bool = True) -> bool:
        """
        Check if the host is reachable by executing a simple command.

        Can optionally raise an exception, which will contain much deeper
        details about the connection failure.

        As such, with raise_on_error set to True, ping() can be used
        to verify authentication and connectivity in general.

        :param raise_on_error: Whether to raise an exception on failure
        :param close_connection: Whether to close the connection after pinging.
            This has no effect if SSH pipelining is enabled, as the connection
            will be managed by the Reaper Thread.

        :return: True if the host is reachable, False otherwise
        """
        try:
            self.logger.debug("Pinging host %s at %s:%s", self.name, self.ip, self.port)
            self.connection.run("true", hide=True)
            self.online = True
        except PasswordRequiredException as e:
            # Paramiko sucks at raising exceptions, and will essentially
            # raise this with message "Private key file is encrypted." whenever
            # *anything* goes wrong during authentication, whenever an agent
            # or keys are involved. Even if it's watching from the bushes.
            #
            # Since this is supremely unhelpful from a UX perspective,
            # We rewrite it to a more informative message.
            self.logger.error(
                "Authentication error for host %s: %s",
                self.name,
                type(e).__name__ + ": " + str(e),
            )
            self.online = False

            if raise_on_error:
                raise OfflineHostError(AUTH_FAILURE_MESSAGE) from e
        except Exception as e:
            self.logger.error("Ping to host %s failed: %s", self.name, e)
            self.online = False

            if raise_on_error:
                raise OfflineHostError(f"{type(e).__name__}: {e}") from e
        finally:
            if close_connection and not app_config["options"]["ssh_pipelining"]:
                self.close()

        return self.online

    def __str__(self):
        if self.online and self.supported:
            status = "Online"
        elif self.online and not self.supported:
            status = "Online (Unsupported)"
        else:
            status = "Offline"

        return (
            f"{self.name} ({self.ip}:{self.port}) "
            f"[{self.os}, {self.version}, {self.flavor}, "
            f"{self.package_manager}], {status}"
        )

    def __repr__(self):
        return f"Host(name='{self.name}', ip='{self.ip}', port='{self.port}')"
