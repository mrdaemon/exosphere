import logging
import re
from typing import Optional

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager


class Apt(PkgManager):
    """
    Apt Package Manager

    Implements the Apt package manager interface.
    """

    def __init__(self, sudo: bool = True, password: Optional[str] = None) -> None:
        """
        Initialize the Apt package manager.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        super().__init__(sudo, password)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Debian Apt package manager")
        self.vulnerable: list[str] = []

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the APT package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        update = cx.sudo("apt-get update", hide=True, warn=True)

        if update.failed:
            return False

        return True

    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Get a list of available updates for APT.

        :param cx: Fabric Connection object.
        :return: List of available updates.
        """

        updates: list[Update] = []

        raw_query = cx.run(
            "apt-get dist-upgrade -s | grep -e '^Inst'", hide=True, warn=True
        )

        if raw_query.failed:
            raise DataRefreshError(
                f"Failed to get updates from apt-get: {raw_query.stderr}"
            )

        for line in raw_query.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            update = self._parse_line(line)
            if update is None:
                continue

            updates.append(update)

        return updates

    def _parse_line(self, line: str) -> Update | None:
        """
        Parse a line from the APT update output.

        :param line: Line from the APT update output.
        :return: Update data class instance or None if parsing fails.
        """

        pattern = (
            r"^Inst\s+"  # Starts with "Inst" followed by space(s)
            r"(\S+)\s+"  # (1) Package name: non-space characters
            r"\[([^\]]+)\]\s+"  # (2) Current version: content inside []
            r"\((\S+)\s+"  # (3) New version: first non-space in ()
            r"(.+?)\s+\[[^\]]+\]\)"  # (4) Repo source: lazily capture text until next [..]
        )

        match = re.match(pattern, line)

        if not match:
            return None

        package_name = match.group(1).strip()
        current_version = match.group(2).strip()
        new_version = match.group(3).strip()
        repo_source = match.group(4).strip()
        is_security = False

        if "security" in repo_source.lower():
            is_security = True

        return Update(
            name=package_name,
            current_version=current_version,
            new_version=new_version,
            source=repo_source,
            security=is_security,
        )
