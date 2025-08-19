"""
Errors Module for Exosphere

This module defines custom exception types used throughout the
Exosphere application.
"""

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
