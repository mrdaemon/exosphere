import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import Callable

import yaml

from exosphere import app_config, app_state, cli
from exosphere.inventory import Configuration

logger = logging.getLogger(__name__)

# List of configuration file paths to check, in order of precedence
# The search stops at first match, so ordering matters.
# TODO: Add support for environment variables
CONFPATHS: list[Path] = [
    Path.home() / ".config" / "exosphere" / "config.yaml",
    Path.home() / ".config" / "exosphere" / "config.toml",
    Path.home() / ".config" / "exosphere" / "config.json",
    Path.home() / ".exosphere.yaml",
    Path.home() / ".exosphere.toml",
    Path.home() / ".exosphere.json",
    Path.cwd() / "config.yaml",
    Path.cwd() / "config.toml",
    Path.cwd() / "config.json",
]

LOADERS: dict[str, Callable] = {
    "yaml": yaml.safe_load,
    "yml": yaml.safe_load,
    "toml": tomllib.load,
    "json": json.load,
}


def setup_logging(log_level: str) -> None:
    """
    Set up logging configuration.
    TODO: This is more or less a placeholder for the root logger.
    It definitely should log to file and other things down the road.

    :param log_level: The logging level to set.
    """
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger(__name__).info("Logging initialized with level: %s", log_level)
    logging.getLogger().setLevel(log_level)


def load_first_config(config: Configuration) -> bool:
    """
    Load the first configuration file found in the list of paths.
    Brutally exits with non-zero status in case of issues beyond
    ENOENT and EISDIR.

    :param config: The configuration object to populate.

    :return: True if a configuration file was loaded, False otherwise.
    """
    for confpath in CONFPATHS:
        logger.debug("Trying config file at %s", confpath)
        if not confpath.exists():
            continue

        logger.debug("Loading config file from %s", confpath)
        ext = confpath.suffix[1:].lower()
        loader = LOADERS.get(ext)

        if not loader:
            logger.error("No working loaders for extension: %s, skipping.", ext)
            continue

        try:
            if config.from_file(filepath=str(confpath), loader=loader, silent=True):
                app_state.confpath = str(confpath)
                logger.info("Loaded config file from %s", confpath)
                return True
        except Exception as e:
            # Abort brutally in case of load failure
            # Exception will contain the actual error message
            logger.error("Startup error: %s", e)
            sys.exit(1)

    return False


def main() -> None:
    """
    Program Entry Point
    """
    # Load the first configuration file found
    if not load_first_config(app_config):
        logger.warning("No configuration file found. Using defaults.")

    # Setup logging from configuration
    setup_logging(app_config["options"]["log_level"])

    # Launch CLI application
    cli.app()


if __name__ == "__main__":
    main()
