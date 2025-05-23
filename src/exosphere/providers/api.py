import logging
from abc import ABC, abstractmethod
from typing import Optional

from fabric import Connection

from exosphere.data import Update


class PkgManager(ABC):
    """
    Abstract Base Class for Package Manager

    Defines the interface for Package Manager implementations.
    """

    def __init__(self, sudo: bool = True, password: Optional[str] = None) -> None:
        """
        Initialize the Package Manager.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        self.sudo = sudo
        self.__password = password

        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    @abstractmethod
    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the package repository.

        This method should be implemented by subclasses to provide
        the specific synchronization logic for different package managers.

        :return: True if synchronization is successful, False otherwise.
        """
        raise NotImplementedError("reposync method is not implemented.")

    @abstractmethod
    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Get a list of available updates.

        This method should be implemented by subclasses to provide
        the specific logic for retrieving updates for different package managers.

        :return: List of available updates.
        """
        raise NotImplementedError("updates method is not implemented.")
