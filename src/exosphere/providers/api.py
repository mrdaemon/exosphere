"""
Providers API

This module defines the abstract base class for package managers as
well as helper functions and decorators to be used by package manager
provider implementations.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from fabric import Connection

from exosphere.data import Update


def requires_sudo(func: Callable) -> Callable:
    """
    Decorator to mark a function as requiring sudo privileges.

    This decorator sets an attribute on the function to indicate that
    it requires sudo privileges to execute. You should add it to any
    method that requires elevated privileges, i.e. whenever you are
    using 'cx.sudo()' instead of 'cx.run()'.
    """
    setattr(func, "__requires_sudo", True)
    return func


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

        # Setup logging
        self.logger = logging.getLogger(
            f"exosphere.providers.{self.__class__.__name__.lower()}"
        )

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
