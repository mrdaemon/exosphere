import inspect
import logging
from datetime import datetime, timezone

from fabric import Connection
from paramiko.ssh_exception import PasswordRequiredException

from exosphere import app_config
from exosphere.data import HostInfo, Update
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

        # Ensure supported member is set for backward compatibility
        if not hasattr(self, "supported"):
            self.supported = True

        # Reset unserializables
        self.logger = logging.getLogger(__name__)
        self._connection = None
        if "package_manager" in state and state.get("supported", False):
            self._pkginst = PkgManagerFactory.create(state["package_manager"])

        # Ensure all parameters with defaults are properly set
        # This helps during version/signature changes.
        signature = inspect.signature(self.__init__)

        for name, param in signature.parameters.items():
            if name == "self":
                continue
            if not hasattr(self, name):
                # Handle optional parameters that are processed in the constructor
                # and use the default value from the configuration if not set
                if name == "connect_timeout":
                    setattr(self, name, app_config["options"]["default_timeout"])
                    continue

                if name == "sudo_policy":
                    setattr(
                        self,
                        name,
                        SudoPolicy(app_config["options"]["default_sudo_policy"]),
                    )
                    continue

                # Handle everything else that eats the default value from the constructor
                if param.default is not inspect.Parameter.empty:
                    setattr(self, name, param.default)
                else:
                    raise ValueError(
                        "Unable to de-serialize Host object state: "
                        f"Missing required parameter '{name}'"
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
            self.ping(raise_on_error=True)
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

        pkg_manager = self._pkginst
        if not pkg_manager.reposync(self.connection):
            raise DataRefreshError(
                f"Failed to sync package repositories on {self.name}"
            )

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

        pkg_manager = self._pkginst
        self.updates = pkg_manager.get_updates(self.connection)

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

    def ping(self, raise_on_error: bool = False) -> bool:
        """
        Check if the host is reachable by executing a simple command.

        Can optionally raise an exception, which will contain much deeper
        details about the connection failure.

        As such, with raise_on_error set to True, ping() can be used
        to verify authentication and connectivity in general.

        :param raise_on_error: Whether to raise an exception on failure

        :return: True if the host is reachable, False otherwise
        """
        try:
            with self.connection as conn:
                self.logger.debug(
                    "Pinging host %s at %s:%s", self.name, self.ip, self.port
                )
                conn.run("true", hide=True)

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
