"""
RedHat Package Manager Provider
"""

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

    def __init__(self, use_yum: bool = False) -> None:
        """
        Initialize the DNF package manager.

        :param use_yum: Use yum instead of dnf for compatibility
        """
        self.pkgbin = "yum" if use_yum else "dnf"
        super().__init__()
        self.logger.debug("Initializing RedHat DNF package manager")

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the DNF package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing dnf repositories")

        with cx as c:
            update = c.run(
                f"{self.pkgbin} makecache --refresh --quiet -y", hide=True, warn=True
            )

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
        with cx as c:
            raw_query = c.run(
                f"{self.pkgbin} check-update --quiet -y", hide=True, warn=True
            )

        if raw_query.return_code == 0:
            self.logger.debug("No updates available")
            return updates

        if raw_query.failed:
            if raw_query.return_code != 100:
                raise DataRefreshError(
                    f"Failed to retrieve updates from DNF: {raw_query.stderr}"
                )

        parsed_tuples: list[tuple[str, str, str]] = []

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

            parsed_tuples.append((name, version, source))

        self.logger.info("Found %d updates", len(parsed_tuples))

        installed_versions = self._get_current_versions(
            cx, [name for name, _, _ in parsed_tuples]
        )

        for name, version, source in parsed_tuples:
            is_security = name in security_updates

            current_version = installed_versions.get(name, "(unknown)")

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

        with cx as c:
            raw_query = c.run(
                f"{self.pkgbin} check-update --security --quiet -y",
                hide=True,
                warn=True,
            )

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

    def _get_current_versions(
        self, cx: Connection, package_names: list[str]
    ) -> dict[str, str]:
        """
        Get the currently installed version of a package.

        :param cx: Fabric Connection object.
        :param package_name: Name of the package.
        :return: Currently installed version of the package.
        """

        with cx as c:
            result = c.run(
                f"{self.pkgbin} list installed --quiet -y {' '.join(package_names)}",
                hide=True,
                warn=True,
            )

        if result.failed:
            raise DataRefreshError(f"Failed to get current versions: {result.stderr}")

        current_versions = {}

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or "Installed Packages" in line:
                continue

            parts = self._parse_line(line)

            if parts is None:
                continue

            name = parts[0]
            version = parts[1]

            # If a package shows up more than once in the list, we just
            # clobber it and keep the last instance.
            # This looks like a bug, but is intended behavior:
            # DNF may list both the old and new versions during some
            # transitions, so we intentionally keep the last listed
            # version for each package.
            current_versions[name] = version

        self.logger.debug("Current versions: %s", current_versions)
        return current_versions


class Yum(Dnf):
    """
    Yum Package Manager

    Implements the Yum package manager interface.
    Wraps Dnf, and is mainly a compatibility layer for older systems.
    Yum and DNF thankfully have identical interfaces, but if any
    disreptancies reveal themselves, they can be implemented here.
    """

    def __init__(self) -> None:
        """
        Initialize the Yum package manager.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        super().__init__(use_yum=True)
