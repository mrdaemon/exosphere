"""
RedHat Package Manager Provider
"""

import re

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager


class Dnf(PkgManager):
    """
    DNF Package Manager

    Implements the DNF package manager interface.
    Can also be used as a drop-in replacement for YUM.

    Some limitations:
     - Current Version data is provided on a Best Effort basis
     - Slotted/installonly packages especially are clobbered down to a
       single version
     - Some broken kernel repo configurations may cause kernel updates
       to not be displayed, but this is a Vendor Specific issue, and
       working around it is not worth the effort as it introduces new
       and exciting issues for systems where this is not the case.
    """

    def __init__(self, use_yum: bool = False) -> None:
        """
        Initialize the DNF package manager.

        :param use_yum: Use yum instead of dnf for compatibility
        """
        self.pkgbin = "yum" if use_yum else "dnf"
        super().__init__()
        self.logger.debug("Initializing RedHat DNF package manager")
        self.security_updates: list[str] = []
        self.line_pattern: re.Pattern | None = None

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the DNF package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing dnf repositories")

        update = cx.run(
            f"{self.pkgbin} --quiet -y makecache --refresh", hide=True, warn=True
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
        self.security_updates = self._get_security_updates(cx)

        # Get all updates
        raw_query = cx.run(
            f"{self.pkgbin} --quiet -y check-update", hide=True, warn=True
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
            if "obsoleting packages" in line.casefold():
                self.logger.debug(
                    "Reached 'Obsoleting Packages' section, stopping parsing."
                )
                break

            # Skip Security: annotation lines emitted by dnf when
            # some intermediate security updates are installed but not active,
            # or similar scenarios
            if line.casefold().startswith("security:"):
                self.logger.debug("Skipping security annotation line: %s", line)
                continue

            parsed = self._parse_line(line)
            if parsed is None:
                self.logger.debug("Failed to parse line: %s. Skipping.", line)
                continue

            name, version, source = parsed

            parsed_tuples.append((name, version, source))

        self.logger.debug("Found %d update(s)", len(parsed_tuples))

        # Skip the rest of processing if no parsable updates were found.
        # This likely indicates an issue with the system, unexpected
        # output, or an issue with our parser needing adjustments.
        if not parsed_tuples:
            self.logger.warning(
                "%s reported updates, but none were extracted! "
                "This is likely a bug, consider filing an issue." % self.pkgbin.upper()
            )
            return updates

        installed_versions = self._get_current_version(
            cx, [name for name, _, _ in parsed_tuples]
        )

        for name, version, source in parsed_tuples:
            is_security = name in self.security_updates

            current_version = installed_versions.get(name, None)

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

        raw_query = cx.run(
            f"{self.pkgbin} --quiet -y check-update --security",
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
            if line.casefold().startswith("obsoleting packages"):
                self.logger.debug(
                    "Reached 'Obsoleting Packages' section, stopping parsing."
                )
                break

            # Skip Security: annotation lines
            if line.casefold().startswith("security:"):
                continue

            parsed = self._parse_line(line)
            if parsed:
                name, version, source = parsed
                updates.append(name)

        self.logger.info("Found %d security updates", len(updates))
        return updates

    def _parse_line(self, line: str) -> tuple[str, str, str] | None:
        """
        Parse a line from DNF check-update style tabular output
        Extracts Update object data as a tuple.

        :param line: Line from DNF output.
        :return: Tuple of (name, version, source) or None if parsing fails.
        """

        # Lazy compile the line pattern on first use
        # Repository source component is usually in the form of "reponame"
        # but can be prefixed with "@" or in the case of missing metadata,
        # be the string "<unknown>" or similar. We account for these here.
        if self.line_pattern is None:
            self.line_pattern = re.compile(
                r"^(?P<name>[a-z0-9][\w+.-]*\.\w+)\s+"  # Package (name.arch)
                r"(?P<version>[\w.+~:-]+-[\w.+~]+)\s+"  # RPM version-release
                r"(?P<source>@?[a-z0-9][\w.:+/-]*|<[^>\s]+>)$",  # Repo source (optional @ or <>
                re.ASCII | re.IGNORECASE,
            )

        match = self.line_pattern.match(line)

        if not match:
            self.logger.debug("Skipping garbage line: %s", line)
            return None

        # Cleanup source string before sending it up
        source = match["source"].removeprefix("@").strip("<>")

        return (match["name"], match["version"], source)

    def _get_current_version(
        self, cx: Connection, package_names: list[str]
    ) -> dict[str, str]:
        """
        Get the currently installed version of a package.

        This method clobbers packages down to a single version.
        For installonly/slotted packages with multiple installed versions,
        the last reported version is used.

        This is done on a best effort basis, but works well enough
        given the limitations of the DNF/YUM interfaces.

        :param cx: Fabric Connection object.
        :param package_names: Package names to return versions for.
        :return: Currently installed version of each package.
        """

        result = cx.run(
            f"{self.pkgbin} --quiet -y list installed {' '.join(package_names)}",
            hide=True,
            warn=True,
        )

        if result.failed:
            raise DataRefreshError(f"Failed to get current versions: {result.stderr}")

        current_versions = {}

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or "installed packages" in line.casefold():
                continue

            # Stop parsing at "Available packages" section
            # This is for DNF5 compatibility, which helpfully lists them
            # and our clobbering logic prevents current version logic from
            # working.
            if "available packages" in line.casefold():
                self.logger.debug(
                    "Reached 'Available packages' section, stopping parsing."
                )
                break

            parts = self._parse_line(line)

            if parts is None:
                continue

            name = parts[0]
            version = parts[1]

            existing_key = current_versions.get(name)

            # Clobber packages down to a single version
            # This handles slotted/installonly packages where multiple
            # versions may be installed concurrently.
            if existing_key:
                self.logger.debug(
                    "Clobbering %s with %s for package %s",
                    existing_key,
                    version,
                    name,
                )

            current_versions[name] = version

        self.logger.debug("Current versions: %s", current_versions)
        return current_versions


class Yum(Dnf):
    """
    Yum Package Manager

    Implements the Yum package manager interface.
    Wraps Dnf, and is mainly a compatibility layer for older systems.
    Yum and DNF thankfully have identical interfaces, but if any
    discrepancies reveal themselves, they can be implemented here.
    """

    def __init__(self) -> None:
        """
        Initialize the Yum package manager.
        """
        super().__init__(use_yum=True)
