"""
This module exists mainly to define common paths for loadables and
other dependent files and resources used at runtime.

This is intended to be multiplatform, and will contain platform
appropriate paths for configuration and state directories.

The constants all contain Path objects, but can be cast to string
as needed.

Example:

    from exosphere import paths

    path = str(fspaths.CONFIG_DIR / "config.yaml") # string path

"""

from pathlib import Path

from platformdirs import (
    user_cache_path,
    user_config_path,
    user_log_path,
    user_state_path,
)

_appname = "exosphere"
_appauthor = False  # Disable appauthor, can do without the extra directory

CONFIG_DIR = user_config_path(appname=_appname, appauthor=_appauthor)
STATE_DIR = user_state_path(appname=_appname, appauthor=_appauthor)
LOG_DIR = user_log_path(appname=_appname, appauthor=_appauthor)
CACHE_DIR = user_cache_path(appname=_appname, appauthor=_appauthor)


def ensure_dirs() -> None:
    """Create all required directories if they do not exist."""
    for d in (CONFIG_DIR, STATE_DIR, LOG_DIR, CACHE_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)


def get_dirs() -> dict[str, str]:
    """Return a dictionary of all directories."""
    return {
        "config": str(CONFIG_DIR),
        "state": str(STATE_DIR),
        "log": str(LOG_DIR),
        "cache": str(CACHE_DIR),
    }


__all__ = ["CONFIG_DIR", "STATE_DIR", "LOG_DIR", "CACHE_DIR", "ensure_dirs", "get_dirs"]
