"""
FreeBSD Pkg Package Manager Provider
"""

import re

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers.api import PkgManager, requires_sudo


class Pkg(PkgManager):
    """
    Package manager for FreeBSD using pkg

    Limitations:
        - Does not include packages changed as a result of a direct dependency
          update, only the top-level packages.
        - Does not include ports, only packages installed via pkg.
        - Does not handle system or kernel updates. Maybe one day we'll wrap
          freebsd-update(8) for that, but for now you get nice emails about these
          anyways, when properly configured, and it's easier to track.
    """

    SUDOERS_COMMANDS: list[str] | None = [
        "/usr/sbin/pkg update -q",
    ]

    def __init__(self) -> None:
        """
        Initialize the Pkg package manager.
        """
        super().__init__()
        self.logger.debug("Initializing FreeBSD pkg package manager")
        self.vulnerable: list[str] = []

    @requires_sudo
    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the package repository.

        This method is equivalent to running 'pkg update -q'.

        :param cx: Fabric Connection object
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing FreeBSD pkg repositories")

        result = cx.sudo("/usr/sbin/pkg update -q", hide=True, warn=True)

        if result.failed:
            self.logger.error(
                f"Failed to synchronize FreeBSD pkg repositories: {result.stderr}"
            )
            return False

        self.logger.debug("FreeBSD pkg repositories synchronized successfully")

        return True

    def get_updates(self, cx: Connection) -> list[Update]:
        """
        Get a list of available updates.

        This method retrieves the list of available updates for FreeBSD
        using the pkg command.

        :param cx: Fabric Connection object
        :return: List of available updates.
        """
        updates: list[Update] = []
        vulnerable: list[str] = []

        # Collect vulnerable packages first
        audit_result = cx.run("pkg audit -q", hide=True, warn=True)

        if audit_result.failed:
            # We check for stderr here, as pkg audit will return
            # non-zero exit code if vulnerable packages are found.
            if audit_result.stderr:
                self.logger.error("pkg audit failed: %s", audit_result.stderr)
                raise DataRefreshError(
                    f"Failed to get vulnerable packages from pkg: {audit_result.stdout} {audit_result.stderr}"
                )

        # Check pkg audit output for known vulnerable packages
        for line in audit_result.stdout.splitlines():
            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            # Add the vulnerable package to the list
            # This is a string, not an Update object.
            # Comparison can be done later via:
            # f"{update.name}-{update.current_version}"
            vulnerable.append(line)

        # Store vulnerable packages as member for later use
        self.vulnerable = vulnerable
        self.logger.debug(
            "Found %d vulnerable packages: %s",
            len(vulnerable),
            ", ".join(vulnerable),
        )

        # Check package updates
        query_result = cx.run("pkg upgrade -qn | grep -e '^\\s'", hide=True, warn=True)

        if query_result.failed:
            # Nonzero exit can mean grep found no matches.
            if query_result.stderr:
                raise DataRefreshError(
                    f"Failed to get updates from pkg: {query_result.stderr}"
                )

            # We're probably good, no updates available.
            self.logger.debug("No updates available or no matches in output.")
            return updates

        for line in query_result.stdout.splitlines():
            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            update = self._parse_line(line)
            if update is None:
                self.logger.debug("Skipping garbage line: %s", line)
                continue

            updates.append(update)

        self.logger.debug(
            "Found %d updates for FreeBSD packages: %s",
            len(updates),
            ", ".join(u.name for u in updates),
        )

        return updates

    def _parse_line(self, line: str) -> Update | None:
        """
        Parse a line from the output of pkg upgrade.

        Extracts the package name, current version, and proposed version.
        Also extracts the repository name in case of recent versions of pkg.
        """

        pattern = (
            r"^\s*(?P<name>\S+):\s+"  # Package name, followed by colon and spaces
            r"(?P<version>[^\s]+)"  # Current version: non-space characters
            r"(?:"  # Start of alternation group
            r"(?:\s+->\s+(?P<new>[^\s]+))?"  # Optional separator and new version
            r")"  # End of alternation group
            r"(?:\s*\[(?P<repo>.*?)\])?"  # Optional repo tag in brackets (e.g., [FreeBSD])
            r"$"  # End of line
        )

        match = re.match(pattern, line)
        if not match:
            return None

        package_name = match["name"].strip()
        pkg_version = match["version"].strip()
        new_version = match["new"].strip() if match["new"] else f"{pkg_version}"
        repo_name = match["repo"].strip() if match["repo"] else "Packages Mirror"

        if match["new"] is None:
            # New package, no ->, treat as such
            self.logger.debug(
                "Found new package %s with version %s", package_name, new_version
            )
            pkg_version = None  # No current version for new packages
            is_security = False  # New packages are not security updates by definition
        else:
            # normal update, check if it's a security update
            is_security = f"{package_name}-{pkg_version}" in self.vulnerable
            if is_security:
                self.logger.debug(
                    "Found vulnerable package %s-%s, marking as security update",
                    package_name,
                    pkg_version,
                )

        return Update(
            name=package_name,
            current_version=pkg_version,
            new_version=new_version,
            source=repo_name,
            security=is_security,
        )
