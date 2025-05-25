import importlib.metadata

from exosphere.data import GlobalState
from exosphere.inventory import Configuration

# Global Instances: configuration and GlobalState
# These are set at runtime and should be used as singletons
# to hold the global state and configuration.

app_state = GlobalState()
app_config = Configuration()  # Has default values out of the box

# Current software version, imported from pyproject metadata
__version__ = importlib.metadata.version("exosphere")

__all__ = ["__version__", "app_state", "app_config"]
