"""
Errors Module for Exosphere

This module defines custom exception types used throughout the
Exosphere application.
"""


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
