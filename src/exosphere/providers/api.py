"""
Providers API

This module defines the abstract base class for package managers as
well as helper functions and decorators to be used by package manager
provider implementations.
"""

import functools
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, MutableMapping
from typing import Any

from fabric import Connection
from invoke.exceptions import AuthFailure

from exosphere.data import Update
from exosphere.errors import SUDO_AUTH_FAILURE_MESSAGE, DataRefreshError


class _HostLogAdapter(logging.LoggerAdapter):
    """
    Logger adapter that prefixes messages with a host name.
    """

    def __init__(self, logger: logging.Logger, host_name: str) -> None:
        super().__init__(logger, {"host": host_name})
        self._host_name = host_name

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        return f"[{self._host_name}] {msg}", kwargs


def requires_sudo(func: Callable) -> Callable:
    """
    Decorator to mark a function as requiring sudo privileges.

    This decorator sets an attribute on the function to indicate that
    it requires sudo privileges to execute. You should add it to any
    method that requires elevated privileges, i.e. whenever you are
    using 'cx.sudo()' instead of 'cx.run()'.

    Additionally, the decorator provides enhanced error handling for
    sudo related failures, presenting a clear message about sudo policies
    and sudoers configuration when an AuthFailure or related exception occurs.
    """

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        try:
            return func(*args, **kwargs)
        except AuthFailure as e:
            raise DataRefreshError(SUDO_AUTH_FAILURE_MESSAGE) from e

    setattr(wrapper, "__requires_sudo", True)
    return wrapper


class PkgManager(ABC):
    """
    Abstract Base Class for Package Manager

    Defines the interface for Package Manager implementations.

    When implementing a Package Manager Provider, you should inherit
    from this class and implement the `reposync` and `get_updates`
    methods.

    .. admonition:: Note

        If either of the methods require elevated privileges, (i.e.,
        they use ``cx.sudo()`` instead of ``cx.run()``), you should
        decorate them with the ``@requires_sudo`` decorator.

    """

    #: List of commands that require sudo privileges.
    #: This will be used by the CLI helper commands to
    #: generate the appropriate sudoers file entries.
    #:
    #: .. code-block:: python
    #:
    #:     SUDOERS_COMMANDS = [
    #:         "/usr/bin/apt-get update",
    #:         "/usr/bin/something-else --with-args -o option=value",
    #:     ]
    #:
    #: If you do not require elevated privileges at all, omit it
    #: entirely from your implementation or set it to `None`.
    SUDOERS_COMMANDS: list[str] | None = None

    def __init__(self) -> None:
        """
        Initialize the Package Manager.
        """

        # Setup logging - base logger is per-provider class.
        # The bind_host() method can later wrap it to add a host prefix
        self._base_logger = logging.getLogger(
            f"exosphere.providers.{self.__class__.__name__.lower()}"
        )
        self.logger: logging.Logger | logging.LoggerAdapter = self._base_logger

    def bind_host(self, host_name: str) -> None:
        """
        Attach host context to this provider's logger.

        :param host_name: Name of the host this provider instance serves.
        """
        self.logger = _HostLogAdapter(self._base_logger, host_name)

    @abstractmethod
    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the package repository.

        This method should be implemented by subclasses to provide
        the specific synchronization logic for different package managers.

        Some package managers may not require explicit synchronization,
        in which case this method can be a no-op that returns True.

        If it is possible to perform the synchronization without
        elevated privileges, it is vastly preferable to do so.

        :param cx: Fabric Connection object
        :return: True if synchronization is successful, False otherwise.
        """
        raise NotImplementedError("reposync method is not implemented.")

    @abstractmethod
    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Get a list of available updates.

        This method should be implemented by subclasses to provide
        the specific logic for retrieving updates for different package managers.

        It is preferable if this can be done without the need for elevated privileges
        and remains read-only, as much as possible.

        :param cx: Fabric Connection object
        :return: List of available updates as Update objects.
        """
        raise NotImplementedError("get_updates method is not implemented.")

    @abstractmethod
    def get_reboot_status(self, cx: Connection) -> bool | None:
        """
        Determine whether the host requires a reboot.

        This method should be implemented by subclasses to detect a
        pending *system* reboot (for example following a kernel or libc
        update). It must be read-only and, like the other query methods,
        avoid elevated privileges wherever possible.

        It should return a boolean corresponding the "has pending
        reboot" status of the host, or ``None`` if the status cannot be
        determined, or if the platform does not have a sensible signal
        for this information.

        Implementations should avoid raising exceptions in failure
        cases, and prefer returning ``None`` instead. Exceptions should
        be reserved for genuine connection-level failures.

        :param cx: Fabric Connection object
        :return: True if a reboot is required, False if not, None if unknown.
        """
        raise NotImplementedError("get_reboot_status method is not implemented.")
