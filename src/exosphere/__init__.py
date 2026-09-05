import importlib.metadata

from .config import Configuration

# Global Instances: configuration and GlobalState
# These are set at runtime and should be used as singletons
# to hold the global state and configuration.

app_config = Configuration()  # Has default values out of the box

# Current software version, imported from pyproject metadata
__version__ = importlib.metadata.version("exosphere_cli")

# Current documentation url, from pyproject metadata
# Falls back to known good readthedocs URL to avoid disasters
_project_urls: list[str] = (
    importlib.metadata.metadata("exosphere_cli").get_all("Project-URL") or []
)

docs_url = next(
    (
        entry.split(",", 1)[1].strip()
        for entry in _project_urls
        if entry.lower().startswith("documentation,")
    ),
    "https://exosphere.readthedocs.io",
)

__all__ = ["__version__", "app_config", "docs_url"]
