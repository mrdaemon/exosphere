import logging
from abc import ABC, abstractmethod

from fabric import Connection

from exosphere.data import Update


class PkgManager(ABC):
    """
    Abstract Base Class for Package Manager

    Defines the interface for Package Manager implementations.
    """

    def __init__(self, sudo: bool = True, password: str | None = None) -> None:
        """
        Initialize the Package Manager.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        self.sudo = sudo
        self.__password = password

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
        :return: List of available updates.
        """
        raise NotImplementedError("updates method is not implemented.")
