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
    def create(name: str, sudo: bool = True, password: str | None = None) -> PkgManager:
        """
        Create a package manager instance based on the provided name.

        :param name: Name of the package manager (e.g., 'apt').
        :param sudo: Whether to use sudo for package operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        :return: An instance of the specified package manager.
        """
        if name not in PkgManagerFactory._REGISTRY:
            raise ValueError(f"Unsupported package manager: {name}")

        pkg_impl = PkgManagerFactory._REGISTRY[name]
        return pkg_impl(sudo=sudo, password=password)
