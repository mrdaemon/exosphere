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
        self.security_updates: list[str] = []

    def reposync(self, cx: Connection) -> bool:
        """
        Synchronize the DNF package repository.

        :param cx: Fabric Connection object.
        :return: True if synchronization is successful, False otherwise.
        """
        self.logger.debug("Synchronizing dnf repositories")

        with cx as c:
            update = c.run(
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

        # Get kernel updates second
        kernel_update = self._get_kernel_updates(cx)
        if kernel_update:
            self.logger.debug("A new kernel is available.")
            updates.append(kernel_update)

        # Get all other updates
        with cx as c:
            raw_query = c.run(
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
            if "obsoleting packages" in line.lower():
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

        self.logger.debug("Found %d update(s)", len(parsed_tuples))

        installed_versions = self._get_current_versions(
            cx, [name for name, _, _ in parsed_tuples]
        )

        for name, version, source in parsed_tuples:
            # If update was provided by security or kernel checks, skip it here
            # Whether it shows up in both lists depends on configuration and
            # this varies from specific flavor to flavor.
            if name in [u.name for u in updates]:
                self.logger.debug(
                    "Update for %s is already in the list, skipping", name
                )
                continue

            is_security = name in self.security_updates

            current_version = installed_versions.get(name, None)

            # Handle slotted packages, if they show up for any reason.
            # We only handle the kernel package as slotted, but it may show
            # up here in some edge cases or configurations.
            if isinstance(current_version, list):
                self.logger.debug(
                    "Slotted package %s has multiple versions: %s",
                    name,
                    current_version,
                )
                current_version = current_version[-1] if current_version else None
                self.logger.debug(
                    "Using version %s for currently installed.", current_version
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

    def _get_kernel_updates(self, cx: Connection) -> Update | None:
        """
        Get latest kernel update if it differs from installed

        This is a separate step due to the way redhat systems usually
        manage kernel images. The packages are essentially slotted,
        and they are New Packages, not straight upgrades in any
        meaningful way.
        """
        self.logger.debug("Querying repository for latest kernel")

        # Format the output to match 'check-update'
        queryformat = "%{name}.%{arch}  %{version}-%{release}  %{repoid}\n"

        with cx as c:
            raw_query = c.run(
                f"{self.pkgbin} --quiet -y repoquery kernel --latest-limit=1 --queryformat='{queryformat}'",
                hide=True,
                warn=True,
            )

        if raw_query.failed:
            raise DataRefreshError(
                f"Failed to retrieve latest kernel from repo: {raw_query.stderr}"
            )

        latest: tuple[str, str, str] | None = None

        for line in raw_query.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            parsed = self._parse_line(line)

            if not parsed:
                self.logger.debug("Failed to parse line: %s. Skipping.", line)
                continue

            latest = parsed
            break  # Only one result is expected anyways.

        if not latest:
            self.logger.warning("Repo query did not return a kernel, skipping check")
            return None

        latest_name, latest_version, latest_source = latest
        self.logger.debug("Latest version is %s", latest_version)

        self.logger.debug("Checking installed kernels")
        installed_kernels = self._get_current_versions(cx, ["kernel"])

        if not installed_kernels:
            self.logger.warning("No installed kernels found? This is likely a bug.")
            return None

        # Kernel packages are ALWAYS slotted, and will always return a list
        installed_versions = [v for k in installed_kernels.values() for v in k]

        if latest_version not in installed_versions:
            # We can generally assume that if a kernel package is
            # present in security updates, it's going to be this one,
            # even though we don't explicitly check and compare the versions.
            is_security: bool = latest_name in self.security_updates

            self.logger.debug("Found new kernel: %s", latest_version)

            self.logger.debug(
                "Kernel %s is %s",
                latest_version,
                "security" if is_security else "not security",
            )

            return Update(
                name=latest_name,
                current_version=installed_versions[-1] if installed_versions else None,
                new_version=latest_version,
                source=latest_source,
                security=is_security,
            )

        return None

    def _get_security_updates(self, cx: Connection) -> list[str]:
        """
        Get updates marked as security from dnf
        """
        self.logger.debug("Getting security updates")

        updates: list[str] = []

        with cx as c:
            raw_query = c.run(
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
        :return: Tuple of (name, version, source) or None if parsing fails.
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
    ) -> dict[str, str | list[str]]:
        """
        Get the currently installed version of a package.

        Kernel packages are handled specially since they are slotted.
        We don't generally care about slotted packages and just clobber it
        down to a single version, but kernel packages are of interest.

        If 'kernel' is in the package_names, the value will be
        a list of versions.

        :param cx: Fabric Connection object.
        :param package_names: Package names to return versions for.
        :return: Currently installed version of the package, or
                 list of installed versions if kernel package.
        """

        with cx as c:
            result = c.run(
                f"{self.pkgbin} --quiet -y list installed {' '.join(package_names)}",
                hide=True,
                warn=True,
            )

        if result.failed:
            raise DataRefreshError(f"Failed to get current versions: {result.stderr}")

        current_versions = {}

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or "installed packages" in line.lower():
                continue

            # Stop parsing at "Available packages" section
            # This is for DNF5 compatibility, which helpfully lists them
            # and our clobbering logic prevents current version logic from
            # working.
            if "available packages" in line.lower():
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

            # Kernel packages are slotted and we want to keep all of them.
            if name.split(".")[0] == "kernel":
                if not existing_key:
                    current_versions[name] = [version]
                else:
                    current_versions[name].append(version)
            else:
                # Everything else gets clobbered because slotted packages
                # generally don't matter from a UX standpoint. We just need
                # the last version in the results.
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

        :param sudo: Whether to use sudo for package refresh operations (default is True).
        :param password: Optional password for sudo operations, if not using NOPASSWD.
        """
        super().__init__(use_yum=True)
