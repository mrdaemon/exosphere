import re
from typing import Optional

from fabric import Connection

from exosphere.data import Update
from exosphere.errors import DataRefreshError

from .api import PkgManager


class Pkg(PkgManager):
    """
    Package manager for FreeBSD using pkg
    """

    def __init__(self, sudo: bool = True, password: Optional[str] = None) -> None:
        """
        Initialize the Pkg package manager.

        On FreeBSD, the reposync operation is not needed as the package
        manager automatically syncs the repositories.

        Additionally, this implementation only covers the freebsd packages.
        Ports and system components are not covered as of now.

        You get a nice email about those, if correctly configured.

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        super().__init__(sudo, password)
        self.logger.debug("Initializing FreeBSD pkg package manager")
        self.vulnerable: list[str] = []

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the package repository.

        FreeBSD automatically syncs the repositories on update checks,
        so this method is more or less a no-op and just returns True.

        :param cx: Fabric Connection object
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug(
            "FreeBSD pkg does not require explicit repository synchronization, returning True"
        )
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

        # Check for vulnerable packages via
        # pkg audit -q
        self.logger.debug("Running pkg audit to inventory vulnerable packages")
        result_audit = cx.run("pkg audit -q", hide=True, warn=True)

        if result_audit.failed:
            # We check for stderr here, as pkg audit will return
            # non-zero exit code if vulnerable packages are found.
            if result_audit.stderr:
                self.logger.error("pkg audit failed: %s", result_audit.stderr)
                cx.close()
                raise DataRefreshError(
                    f"Failed to get vulnerable packages from pkg: {result_audit.stdout} {result_audit.stderr}"
                )

        for line in result_audit.stdout.splitlines():
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

        result = cx.run("pkg upgrade -qn | grep -e '^\\s'", hide=True, warn=True)

        if result.failed:
            cx.close()
            # Nonzero exit can mean grep found no matches.
            if result.stderr:
                raise DataRefreshError(
                    f"Failed to get updates from pkg: {result.stderr}"
                )

            # We're probably good, no updates available.
            self.logger.debug("No updates available or no matches in output.")
            return updates

        for line in result.stdout.splitlines():
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

        cx.close()
        return updates

    def _parse_line(self, line: str) -> Update | None:
        """
        Parse a line from the output of pkg upgrade.

        Extracts the package name, current version, and proposed version.
        """

        pattern = (
            r"^\s*(\S+):\s+"  # (1) Package name, followed by colon and spaces
            r"([^\s]+)"  # (2) Current version: non-space characters
            r"\s+->\s+"  # -> Separator, surrounded by spaces
            r"([^\s]+)$"  # (3) Proposed version, non-space characters until eol
        )

        match = re.match(pattern, line)
        if not match:
            return None

        package_name = match.group(1).strip()
        current_version = match.group(2).strip()
        new_version = match.group(3).strip()
        is_security = False

        # Check if package is vulnerable, indicates
        # that it is a security update
        if f"{package_name}-{current_version}" in self.vulnerable:
            self.logger.debug(
                "Found vulnerable package %s-%s, marking as security update",
                package_name,
                current_version,
            )
            is_security = True

        return Update(
            name=package_name,
            current_version=current_version,
            new_version=new_version,
            source="Packages Mirror",  # FreeBSD only has this source
            security=is_security,
        )
