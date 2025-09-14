"""
OpenBSD Pkg Package Manager Provider
"""

import re

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager


class PkgAdd(PkgManager):
    """
    Package manager for OpenBSD using pkg_add

    Limitations:
        - Does not check security state at all if system is tracking -current,
          as it then behaves like a rolling release and there is no way to tell
        - On stable/release, all updates are assumed to be security updates,
          as OpenBSD only ever updates packages for security issues.
        - Thouroughly untested on more exotic architectures where syspatch
          may not be available or fail in different ways. Bug reports welcome!
    """

    def __init__(self) -> None:
        """
        Initialize the PkgOpenBSD package manager.
        """
        super().__init__()
        self.logger.debug("Initializing OpenBSD pkg_add package manager")

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the package repository

        By default, OpenBSD does not require a separate step for this
        and queries the pkg mirrors directly.

        This step is essentially a no-op.

        :param cx: Fabric Connection object
        :return: True if synchronization is successful, False otherwise.
        """

        self.logger.debug("OpenBSD pkg_add does not require repository sync.")
        return True

    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Retrieve the list of available updates.

        This method retrieves the list of available package updates for OpenBSD
        using the 'pkg_add' command.

        :param cx: Fabric Connection object
        :return: List of Update objects
        """

        updates: list[Update] = []
        is_current = False  # Whether or not the system is tracking -current or -beta

        # Run queries within the same connection
        with cx as c:
            version_query = c.run("/usr/sbin/syspatch -l", hide=True, warn=True)
            packages_query = c.run(
                "/usr/sbin/pkg_add -u -v -x -n | grep -e '^Update candidate'",
                hide=True,
                warn=True,
            )

        # Syspatch returns non-zero exit code if the release is unsupported,
        # and we use this to determine if we can track security status.
        if version_query.failed:
            if "unsupported release" in version_query.stderr.lower():
                self.logger.warning(
                    "Host is running unsupported OpenBSD release. "
                    "Security status will not be tracked.",
                )
                is_current = True
            else:
                # Call to syspatch failed unexpectedly
                raise DataRefreshError(
                    f"Failed to query OpenBSD version: {version_query.stderr}"
                )

        # grep will return 1 if there are no candidates at all
        if packages_query.failed:
            if (
                packages_query.return_code == 1
                and not packages_query.stdout
                and packages_query.stderr == "pkg_add should be run as root\n"
            ):
                self.logger.debug("No OpenBSD packages with updates.")
                return updates

            # Call to pkg_add failed unexpectedly
            raise DataRefreshError(
                f"Failed to query OpenBSD pkg_add updates: {packages_query.stderr}"
            )

        # Parse output and filter out packages that don't actually change version
        for line in packages_query.stdout.splitlines():
            line = line.strip()

            # Skip blanks
            if not line:
                continue

            update = self._parse_line(line, is_current=is_current)

            if update is None:
                continue

            updates.append(update)

        self.logger.debug(
            "Found %d updates for OpenBSD packages: %s",
            len(updates),
            ", ".join([u.name for u in updates]),
        )

        return updates

    def _parse_line(self, line: str, is_current: bool = False) -> Update | None:
        """
        Parse a line of pkg_add output to extract update information.

        We do this fairly clumsily and just return None if either:

        - We can't parse that at all
        - The current and new version are the same (no actual update)

        :param line: A line from pkg_add output
        :return: An Update object or None if not an update
        """

        pattern = r"^Update candidates: ([\w\-.+]+)-([^\s]+) -> ([\w\-.+]+)-([^\s]+)$"

        match = re.match(pattern, line)

        if not match:
            self.logger.debug("Could not parse: %s", line)
            return None

        package_name = match.group(1)
        current_version = match.group(2)
        new_name = match.group(3)
        new_version = match.group(4)

        if package_name != new_name:
            self.logger.warning(
                "Unexpected package name change: %s -> %s , ignoring.",
                package_name,
                new_name,
            )
            return None

        if current_version == new_version:
            self.logger.debug(
                "No version change for %s: %s -> %s , ignoring.",
                package_name,
                current_version,
                new_version,
            )
            return None

        self.logger.debug(
            "Parsed update: %s from %s to %s",
            package_name,
            current_version,
            new_version,
        )

        return Update(
            name=package_name,
            current_version=current_version,
            new_version=new_version,
            security=not is_current,  # All updates are security unless on -current
            source="Packages Mirror",
        )
