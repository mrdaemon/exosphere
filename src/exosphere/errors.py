# Exception Types


class DataRefreshError(Exception):
    """Exception raised for errors encountered during data refresh."""

    def __init__(self, message: str, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(self, message)


class UnsupportedOSError(DataRefreshError):
    """Exception raised for unsupported operating systems."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class OfflineHostError(DataRefreshError):
    """Exception raised for offline hosts."""

    def __init__(self, message: str = "Host is offline") -> None:
        super().__init__(message)
