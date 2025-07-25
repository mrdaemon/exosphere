"""
Debian/Ubuntu Apt Package Manager Provider
"""

import re

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager, requires_sudo


class Apt(PkgManager):
    """
    Apt Package Manager

    Implements the Apt package manager interface.
    """

    SUDOERS_COMMANDS: list[str] | None = [
        "/usr/bin/apt-get update",
    ]

    def __init__(self) -> None:
        """
        Initialize the Apt package manager.
        """
        super().__init__()
        self.logger.debug("Initializing Debian Apt package manager")

    @requires_sudo
    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the APT package repository.

        This method is equivalent to running 'apt-get update'.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing apt repositories")

        with cx as c:
            update = c.sudo("apt-get update", hide=True, warn=True)

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

        with cx as c:
            raw_query = c.run(
                "apt-get dist-upgrade -s | grep -e '^Inst'", hide=True, warn=True
            )

        if raw_query.failed:
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

        return updates

    def _parse_line(self, line: str) -> Update | None:
        """
        Parse a line from the APT update output.

        :param line: Line from the APT update output.
        :return: Update data class instance or None if parsing fails.
        """

        pattern = (
            r"^Inst\s+"  # Starts with "Inst" followed by space(s)
            r"(?P<name>\S+)\s+"  # Package name: non-space characters
            r"(?:\[(?P<current_version>[^\]]+)\]\s+)?"  # Current version: text in [] (optional)
            r"\((?P<new_version>\S+)\s+"  # New version: first non-space in ()
            r"(?P<source>.+?)\s+\[[^\]]+\]\)"  # Repo source: lazily capture text until next [..]
        )

        match = re.match(pattern, line)

        if not match:
            return None

        # If current version is empty, treat match as a new package
        if not match["current_version"]:
            self.logger.debug(
                "New package detected: %s (%s)", match["name"], match["new_version"]
            )

        package_name = match["name"].strip()
        current_version = (
            match["current_version"].strip() if match["current_version"] else None
        )
        new_version = match["new_version"].strip()
        repo_source = match["source"].strip()
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
