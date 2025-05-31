from typing import Optional

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager


class Dnf(PkgManager):
    """
    DNF Package Manager

    Implements the DNF package manager interface.
    Can also be used as a drop-in replacement for YUM.

    The whole RPM ecosystem is kind of a piece of shit in terms of
    integration between high level and low level interfaces.
    It is what it is.
    """

    def __init__(self, sudo: bool = True, password: Optional[str] = None) -> None:
        """
        Initialize the DNF package manager.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        super().__init__(sudo, password)
        self.logger.debug("Initializing RedHat DNF package manager")

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the DNF package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing dnf repositories")
        update = cx.run("dnf makecache", hide=True, warn=True)

        if update.failed:
            self.logger.error(
                f"Failed to synchronize dnf repositories: {update.stderr}"
            )
            return False

        self.logger.debug("DNF repositories synchronized successfully")
        return True

    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Get a list of available updates for DNF.

        :param cx: Fabric Connection object.
        :return: List of available updates.
        """

        updates: list[Update] = []

        # Get security updates first
        security_updates = self._get_security_updates(cx)

        # Get all other updates
        raw_query = cx.run("dnf check-update --refresh --quiet", hide=True, warn=True)

        if raw_query.return_code == 0:
            self.logger.debug("No updates available")
            return updates

        if raw_query.failed:
            if raw_query.return_code != 100:
                raise DataRefreshError(
                    f"Failed to retrieve updates from DNF: {raw_query.stderr}"
                )

        for line in raw_query.stdout.splitlines():
            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            # Stop processing at "Obsoleting Packages" section
            if line.startswith("Obsoleting Packages"):
                self.logger.debug(
                    "Reached 'Obsoleting Packages' section, stopping parsing."
                )
                break

            parsed = self._parse_line(line)
            if parsed is None:
                self.logger.debug("Failed to parse line: %s. Skipping.", line)
                continue

            name, version, source = parsed
            is_security = name in security_updates

            current_version = self._get_current_versions(cx, name)

            self.logger.debug(
                "Found security update: %s (current: %s, new: %s, source: %s, security: %s)",
                name,
                current_version,
                version,
                source,
                is_security,
            )

            update = Update(
                name=name,
                current_version=current_version,
                new_version=version,
                source=source,
                security=is_security,
            )

            updates.append(update)

        return updates

    def _get_security_updates(self, cx: Connection) -> list[str]:
        """
        Get updates marked as security from dnf
        """
        self.logger.debug("Getting security updates")

        updates: list[str] = []

        raw_query = cx.run("dnf check-update --security --quiet")

        if raw_query.return_code == 0:
            self.logger.debug("No security updates available")
            return updates

        if raw_query.failed:
            if raw_query.return_code != 100:
                raise DataRefreshError(
                    f"Failed to retrieve security updates from DNF: {raw_query.stderr}"
                )

        self.logger.debug("Parsing security updates")
        for line in raw_query.stdout.splitlines():
            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            # Stop processing at "Obsoleting Packages" section
            if line.startswith("Obsoleting Packages"):
                self.logger.debug(
                    "Reached 'Obsoleting Packages' section, stopping parsing."
                )
                break

            parsed = self._parse_line(line)
            if parsed:
                name, version, source = parsed
                updates.append(name)

        self.logger.info("Found %d security updates", len(updates))
        return updates

    def _parse_line(self, line: str) -> tuple[str, str, str] | None:
        """
        Parse a line from the DNF output to create an Update object.

        :param line: Line from DNF output.
        :return: Update object or None if parsing fails.
        """
        parts = line.split()

        if len(parts) < 3:
            self.logger.debug("Line does not contain enough parts: %s", line)
            return None

        name = parts[0]
        version = parts[1]
        source = parts[2]

        return (name, version, source)

    def _get_current_versions(self, cx: Connection, package_name: str) -> str:
        """
        Get the currently installed version of a package.

        :param cx: Fabric Connection object.
        :param package_name: Name of the package.
        :return: Currently installed version of the package.
        """
        result = cx.run(
            f"dnf list installed --quiet {package_name}", hide=True, warn=True
        )

        if result.failed:
            raise DataRefreshError(
                f"Failed to get current version for {package_name}: {result.stderr}"
            )

        versions = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith(package_name):
                version_set = self._parse_line(line)
                if version_set:
                    versions.append(version_set[1])

        if len(versions) > 1:
            self.logger.debug(
                "Found multiple versions for %s: %s", package_name, ", ".join(versions)
            )
            # Return the last version in list
            return f"{versions[-1]} (+)"

        if versions:
            self.logger.debug(
                "Found current version for %s: %s", package_name, versions[0]
            )
            return versions[0]

        return "(none)"
