"""
Errors Module for Exosphere

This module defines custom exception types used throughout the
Exosphere application, along with presentation helpers that rewrite
inscrutable upstream error messages into something a human can act on.
"""

from cyclopts.exceptions import CycloptsError, UnusedCliTokensError
from cyclopts.panel import CycloptsPanel

# Standard authentication error message for better UX
# This is intended to be displayed whenever Paramiko raises
# PasswordRequiredException, which is nearly always, and has the
# most inscrutable error message known to man.
AUTH_FAILURE_MESSAGE = (
    "Auth Failure. "
    "Verify that keypair authentication is enabled on the server, "
    "that your agent is running with the correct keys loaded, "
    "and that your username is correct for the host."
)

# Sudo authentication failure message for better UX
# This is intended to be displayed whenever a sudo command fails due to
# a password prompt, or failure raised by Invoke's AuthFailure exception.
# This will generally come up when a user is not configured with passwordless
# sudo, but has a Sudo Policy of NOPASSWD or equivalent.
SUDO_AUTH_FAILURE_MESSAGE = (
    "Sudo failed: "
    "Ensure the user is configured with passwordless sudo. "
    "You can use 'exosphere sudo generate' to produce a sudoers snippet for this host. "
    "See: https://exosphere.readthedocs.io/en/stable/connections.html#id1"
)


def error_formatter(error: CycloptsError):
    """
    Render runtime CLI errors, rewording certain messages for friendliness.

    Currently only rewords the default message for unused tokens, which
    is an inscrutable "Unused Tokens: ['foo', 'bar']" dump.

    This otherwise works very much like a pass-through for anything it
    doesn't touch, using the styling CycloptsPanel was configured
    with during App setup.

    :param error: The CycloptsError to handle
    :return: a Renderable with the error object
    """
    if isinstance(error, UnusedCliTokensError):
        tokens = ", ".join(error.unused_tokens or [])
        return CycloptsPanel(
            CycloptsError(
                msg=f"Unexpected argument(s): {tokens}. See --help for usage.",
                console=error.console,
                command_chain=error.command_chain,
            )
        )

    return CycloptsPanel(error)


class DataRefreshError(Exception):
    """Exception raised for errors encountered during data refresh."""

    def __init__(self, message: str, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message)

    def __str__(self) -> str:
        return str(self.args[-1]) if self.args else super().__str__()


class UnsupportedOSError(DataRefreshError):
    """Exception raised for unsupported operating systems."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class OfflineHostError(DataRefreshError):
    """Exception raised for offline hosts."""

    def __init__(self, message: str = "Host is offline or unreachable") -> None:
        super().__init__(message)
