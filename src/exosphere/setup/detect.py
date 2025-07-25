"""
Detection Module

This module contains tasks to detect platform and details about remote
systems. Its role is primarily in discovery and setup actions to
determine platform, operating system and other relevant platform data.
"""

import logging

from fabric import Connection

from exosphere.data import HostInfo
from exosphere.errors import DataRefreshError, OfflineHostError, UnsupportedOSError

SUPPORTED_PLATFORMS = ["linux", "freebsd"]
SUPPORTED_FLAVORS = ["ubuntu", "debian", "rhel", "freebsd"]

logger: logging.Logger = logging.getLogger(__name__)


def platform_detect(cx: Connection) -> HostInfo:
    """
    Detect the platform of the remote system.
    Entry point for refreshing all platform details.

    :param cx: Fabric Connection object
    :return: HostInfo object with platform details
    """

    try:
        result_os = os_detect(cx)
        result_flavor = flavor_detect(cx, result_os)
        result_version = version_detect(cx, result_flavor)
        result_package_manager = package_manager_detect(cx, result_flavor)
    except TimeoutError as e:
        raise OfflineHostError(f"Host {cx.host} is offline. Error: {e}") from e

    return HostInfo(
        os=result_os,
        version=result_version,
        flavor=result_flavor,
        package_manager=result_package_manager,
    )


def os_detect(cx: Connection) -> str:
    """
    Detect the operating system of the remote system.

    :param cx: Fabric Connection object
    :return: OS name as string
    """
    with cx as c:
        result_system = c.run("uname -s", hide=True, warn=True)

    if result_system.failed:
        raise DataRefreshError(f"Failed to query OS info: {result_system.stderr}")

    return result_system.stdout.strip().lower()


def flavor_detect(cx: Connection, platform_name: str) -> str:
    """
    Detect the flavor of the remote system.

    :param cx: Fabric Connection object
    :return: Flavor string
    """

    # Check if platform is one of the supported types
    if platform_name.lower() not in SUPPORTED_PLATFORMS:
        raise UnsupportedOSError(f"Unsupported platform: {platform_name}")

    # FreeBSD doesn't have flavors that matter so far.
    # So we just put "freebsd" in there.
    if platform_name == "freebsd":
        return "freebsd"

    # Linux
    if platform_name == "linux":
        # We're just going to query /etc/os-release directly.
        # Using lsb_release would be better, but it's less available
        #
        with cx as c:
            result_id = c.run("grep ^ID= /etc/os-release", hide=True, warn=True)
            result_like_id = c.run(
                "grep ^ID_LIKE= /etc/os-release",
                hide=True,
                warn=True,
            )

        if result_id.failed:
            raise DataRefreshError(
                "Failed to detect OS flavor via lsb identifier.",
                stderr=result_id.stderr,
                stdout=result_id.stdout,
            )

        # We kind of handwave the specific detection here, as long
        # as either the ID or the LIKE_ID matches, it's supported.
        try:
            actual_id: str = (
                result_id.stdout.strip().partition("=")[2].strip('"').lower()
            )
        except (ValueError, IndexError):
            raise DataRefreshError(
                "Could not parse ID value, likely unsupported.",
                stderr=result_id.stderr,
                stdout=result_id.stdout,
            )

        if actual_id in SUPPORTED_FLAVORS:
            return actual_id

        # If the ID was not a match, we should check the LIKE_ID field.
        # We should resist the temptation to guess, if that fails entirely.
        if result_like_id.failed:
            raise UnsupportedOSError("Unknown flavor, and no ID_LIKE available.")

        # Compare any values found in LIKE_ID to supported flavors.
        # First match is good enough.
        try:
            like_id: str = result_like_id.stdout.strip().partition("=")[2].strip('"')
        except (ValueError, IndexError):
            raise DataRefreshError(
                "Could not parse ID_LIKE value, likely unsupported.",
                stderr=result_like_id.stderr,
                stdout=result_like_id.stdout,
            )

        for like in [x.lower() for x in like_id.split()]:
            if like in SUPPORTED_FLAVORS:
                return like

        # Ultimately, we should give up here since we have no idea
        # what we're talking to, so let the user figure it out.
        raise UnsupportedOSError(
            f"Unsupported OS flavor detected: {result_id.stdout.strip().lower()}"
        )

    raise UnsupportedOSError(f"Unknown issue in detecting platform: {platform_name}")


def version_detect(cx: Connection, flavor_name: str) -> str:
    """
    Detect the version of the remote system.
    :param cx: Fabric Connection object
    :return: Version string
    """

    if flavor_name.lower() not in SUPPORTED_FLAVORS:
        raise UnsupportedOSError(f"Unsupported OS flavor: {flavor_name}")

    # Debian/Ubuntu
    if flavor_name in ["ubuntu", "debian"]:
        with cx as c:
            result_version = c.run("lsb_release -s -r", hide=True, warn=True)

        if result_version.failed:
            raise DataRefreshError(
                "Failed to detect OS version via lsb_release.",
                stderr=result_version.stderr,
                stdout=result_version.stdout,
            )

        return result_version.stdout.strip()

    # Redhat-likes
    if flavor_name == "rhel":
        with cx as c:
            result_version = c.run(
                "grep ^VERSION_ID= /etc/os-release", hide=True, warn=True
            )

        if result_version.failed:
            raise DataRefreshError(
                "Failed to detect OS version via os-release VERSION_ID.",
                stderr=result_version.stderr,
                stdout=result_version.stdout,
            )

        return result_version.stdout.strip().split('"')[1::2][0].lower()

    # FreeBSD
    if flavor_name == "freebsd":
        with cx as c:
            result_version = c.run("/bin/freebsd-version -u", hide=True, warn=True)

        if result_version.failed:
            raise DataRefreshError(
                "Failed to detect OS version via freebsd-version.",
                stderr=result_version.stderr,
                stdout=result_version.stdout,
            )

        return result_version.stdout.strip()

    raise UnsupportedOSError(
        f"Unknown issue in detecting version for flavor: {flavor_name}"
    )


def package_manager_detect(cx: Connection, flavor_name: str) -> str:
    """
    Detect the package manager of the remote system.

    :param cx: Fabric Connection object
    :return: Package manager string
    """

    if flavor_name not in SUPPORTED_FLAVORS:
        raise UnsupportedOSError(f"Unsupported OS flavor: {flavor_name}")

    # Debian/Ubuntu
    if flavor_name in ["ubuntu", "debian"]:
        return "apt"

    # Redhat-likes
    if flavor_name == "rhel":
        with cx as c:
            result_dnf = c.run("command -v dnf", hide=True, warn=True)
            result_yum = c.run("command -v yum", hide=True, warn=True)

        if result_dnf.failed and result_yum.failed:
            raise UnsupportedOSError(
                f"Neither dnf nor yum found on flavor {flavor_name}, unsupported?",
            )

        if not result_dnf.failed:
            return "dnf"

        return "yum"

    # FreeBSD
    if flavor_name == "freebsd":
        return "pkg"

    raise UnsupportedOSError(
        f"Unknown issue in detecting package manager for flavor: {flavor_name}"
    )
