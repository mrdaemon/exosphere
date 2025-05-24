from typing import Optional

from exosphere.providers.api import PkgManager
from exosphere.providers.debian import Apt
from exosphere.providers.freebsd import Pkg


class PkgManagerFactory:
    """
    Factory class for creating package manager instances.
    """

    @staticmethod
    def create(
        name: str, sudo: bool = True, password: Optional[str] = None
    ) -> PkgManager:
        """
        Create a package manager instance based on the provided name.

        :param name: Name of the package manager (e.g., 'apt').
        :param sudo: Whether to use sudo for package operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        :return: An instance of the specified package manager.
        """
        if name == "apt":
            return Apt(sudo=sudo, password=password)
        elif name == "pkg":
            return Pkg(sudo=sudo, password=password)
        else:
            raise ValueError(f"Unsupported package manager: {name}")
