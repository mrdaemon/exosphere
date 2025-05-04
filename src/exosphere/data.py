# Data Types and Classes

from dataclasses import dataclass
from fabric import Connection

from exosphere.errors import OfflineHostError
from exosphere.setup import detect


@dataclass
class HostInfo:
    """
    Data class to hold platform information about a host.
    This includes the operating system, version, and package manager.
    """

    os: str
    version: str
    flavor: str
    package_manager: str


class Host:
    def __init__(self, name: str, ip: str, port: int = 22) -> None:
        self.name = name
        self.ip = ip
        self.port = port

        self._connection = None

        self.online = True

        self.os = (None,)
        self.version = None
        self.flavor = None
        self.package_manager = None

    @property
    def connection(self) -> Connection:
        """
        Establish a connection to the host using Fabric.
        This method sets up the connection object for further operations.

        :return: None
        """
        if self._connection is None:
            self._connection = Connection(host=self.ip, port=self.port)

        return self._connection

    def sync(self) -> None:
        """
        Synchronize host information with remote system.
        Effectively refreshes cache for host information.

        :return: None
        """
        try:
            platform_info: HostInfo = detect.platform_detect(self.connection)
        except OfflineHostError:
            self.online = False
            return

        self.os = platform_info.os
        self.version = platform_info.version
        self.flavor = platform_info.flavor
        self.package_manager = platform_info.package_manager

    def __repr__(self):
        return f"Host(name={self.name}, ip={self.ip}, port={self.port})"
