"""
Package Manager Factory Module

This module provides a factory class for creating instances of a
package manager based on a string based name.

It is used through the application resolve a package name to a concrete
class of a package manager provider implementation.
"""

from exosphere.providers.api import PkgManager
from exosphere.providers.debian import Apt
from exosphere.providers.freebsd import Pkg
from exosphere.providers.redhat import Dnf, Yum


class PkgManagerFactory:
    """
    Factory class for creating package manager instances.
    """

    _REGISTRY = {
        "apt": Apt,
        "pkg": Pkg,
        "dnf": Dnf,
        "yum": Yum,
    }

    @staticmethod
    def get_registry() -> dict[str, PkgManager]:
        """
        Get the registry of available package manager implementations.

        :return: Dictionary of package manager class names keyed by their names.
        """
        return PkgManagerFactory._REGISTRY.copy()

    @staticmethod
    def create(name: str) -> PkgManager:
        """
        Create a package manager instance based on the provided name.

        :param name: Name of the package manager (e.g., 'apt').
        :return: An instance of the specified package manager.
        """
        if name not in PkgManagerFactory._REGISTRY:
            raise ValueError(f"Unsupported package manager: {name}")

        pkg_impl = PkgManagerFactory._REGISTRY[name]
        return pkg_impl()
