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
        self.logger.debug("Initializing Debian Apt package manager")
        self.vulnerable: list[str] = []

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the APT package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing apt repositories")
        update = cx.sudo("apt-get update", hide=True, warn=True)

        if update.failed:
            self.logger.error(
                f"Failed to synchronize apt repositories: {update.stderr}"
            )
            return False

        self.logger.debug("Apt repositories synchronized successfully")

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
            cx.close()

            # Nonzero exit can mean grep found no matches.
            if raw_query.stderr:
                raise DataRefreshError(
                    f"Failed to get updates from apt-get: {raw_query.stderr}"
                )

            # We're probably good, no updates available.
            self.logger.debug("No updates available or no matches in output.")
            return updates

        for line in raw_query.stdout.splitlines():
            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            update = self._parse_line(line)
            if update is None:
                self.logger.debug("Failed to parse line: %s. Skipping.", line)
                continue

            updates.append(update)

        self.logger.debug(
            "Found %d package updates available: %s",
            len(updates),
            ", ".join(u.name for u in updates),
        )

        cx.close()
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
            self.logger.debug(
                f"Package {package_name} is a security update: {new_version}"
            )
            is_security = True

        return Update(
            name=package_name,
            current_version=current_version,
            new_version=new_version,
            source=repo_source,
            security=is_security,
        )
