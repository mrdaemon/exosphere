from exosphere.data import HostInfo
from exosphere.errors import OfflineHostError
from exosphere.setup import detect

from fabric import Connection


class Host:
    def __init__(self, name: str, ip: str, port: int = 22) -> None:
        self.name = name
        self.ip = ip
        self.port = port

        self._connection = None

        self.online = True

        self.os = None
        self.version = None
        self.flavor = None
        self.package_manager = None

    @property
    def connection(self) -> Connection:
        """
        Establish a connection to the host using Fabric.
        This method sets up the connection object for further operations.

        Connection objects are recycled if already created.

        :return: Fabric Connection object
        :raises ConnectionError: If the connection cannot be established
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

    def ping(self) -> bool:
        """
        Check if the host is reachable.

        :return: True if the host is reachable, False otherwise
        """
        try:
            self.connection.run("echo 'ping'", hide=True)
            self.online = True
        except Exception:
            self.online = False
        finally:
            self.connection.close()
            return self.online

    def __str__(self):
        return (
            f"{self.name} ({self.ip}:{self.port}) "
            f"[{self.os}, {self.version}, {self.flavor}, "
            f"{self.package_manager}], {'Online' if self.online else 'Offline'}"
        )

    def __repr__(self):
        return f"Host({self.name}, {self.ip}, {self.port})"
