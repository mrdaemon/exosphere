# Detection Module
# This module contains tasks to detect platform and details about
# the remote system. It is used mostly for setup actions surrounding
# actual actions exosphere might take.

from fabric import Connection

from exosphere.data import HostInfo
from exosphere.errors import DataRefreshError, UnsupportedOSError


SUPPORTED_PLATFORMS = ["linux", "freebsd"]
SUPPORTED_FLAVORS = ["ubuntu", "debian", "redhat"]


def platform_detect(cx: Connection) -> HostInfo:
    """
    Detect the platform of the remote system.
    Entry point for refreshing all platform details.

    :param cx: Fabric Connection object
    :return: Dictionary with platform details
    """

    results = {}

    result_os = os_detect(cx)
    result_flavor = flavor_detect(cx, result_os)
    result_version = version_detect(cx, result_os)


def os_detect(cx: Connection) -> str:
    result_system = cx.run("uname -s", hide=True)

    if result_system.failed:
        raise DataRefreshError("Failed to query OS info.")

    return result_system.stdout.strip().lower()


def flavor_detect(cx: Connection, platform: str) -> str:
    """
    Detect the flavor of the remote system.
    :param cx: Fabric Connection object
    :return: Flavor string
    """

    # Check if platform is one of the supported types
    if platform not in SUPPORTED_PLATFORMS:
        raise UnsupportedOSError(f"Unsupported platform: {platform}")

    # FreeBSD doesn't have flavors that matter so far.
    # So we just put "freebsd" in there.
    if platform == "freebsd":
        return "freebsd"

    # Linux
    if platform == "linux":
        # We're just going to query /etc/os-release directly.
        # Using lsb_release would be better, but it's less available
        #
        result_id = cx.run("grep ^ID= /etc/os-release", hide=True, warn=True)
        result_like_id = cx.run(
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
        actual_id = result_id.stdout.strip().split('"')[1::2][0].lower()
        if actual_id in SUPPORTED_FLAVORS:
            return actual_id

        # If the ID was not a match, we should check the LIKE_ID field.
        # We should resist the temptation to guess, in this case.
        if result_like_id.failed:
            raise UnsupportedOSError("Unknown flavor, no matching ID or ID_LIKE.")

        # Return first match in like table, it's good enough
        like_id = result_like_id.stdout.strip().split('"')[1::2]
        for like in [x.lower() for x in like_id]:
            if like in SUPPORTED_FLAVORS:
                return like

        # Ultimately, we should give up here since we have no idea
        # what we're talking to, so let the user figure it out.
        raise UnsupportedOSError(
            f"Unsupported OS flavor detected: {actual_id.stdout.strip().lower()}"
        )


def version_detect(cx: Connection, platform: str) -> str:
    """
    Detect the version of the remote system.
    :param cx: Fabric Connection object
    :return: Version string
    """

    # Check if platform is one of the supported types
    if platform not in SUPPORTED_PLATFORMS:
        raise UnsupportedOSError(platform)

    # Linux
