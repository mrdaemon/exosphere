"""
Main Module for Exosphere

Entry point and initialization logic for the application.
This module is responsible for:

- Setting up logging
- Loading configuration files
- Initializing the inventory
- Setting up the application environment and context
- Entering the CLI entrypoint

"""

import atexit
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from filelock import FileLock, Timeout
from rich.traceback import install as install_rich_traceback

from exosphere import app_config, cli, context, fspaths
from exosphere.commands.utils import err_console
from exosphere.config import KNOWN_LOADERS, Configuration
from exosphere.inventory import Inventory
from exosphere.pipelining import ConnectionReaper

logger = logging.getLogger(__name__)

# Configuration file names to check, in order of precedence.
# The search stops at first match, so ordering matters.
CONFIG_FILENAMES: tuple[str, ...] = (
    "config.yaml",
    "config.yml",
    "config.toml",
    "config.json",
)


def config_paths(base: Path) -> list[Path]:
    """
    Build the ordered list of candidate config file paths under ``base``.

    Resolved at call time to ensure we get the correct base path
    in case of environment variable override or other dynamic changes.
    """
    return [base / name for name in CONFIG_FILENAMES]


def setup_logging(log_level: str, log_file: str | None = None) -> None:
    """
    Set up logging configuration.
    This function initializes the logging system with a specified log level
    and optional log file. If no log file is specified, logs will be printed
    to the console. This is useful for debugging and running in the REPL.

    :param log_file: Optional log file path to write logs to.
    :param log_level: The logging level to set.
    """
    handler: logging.Handler

    # Normalize log level to UPPERCASE
    log_level = log_level.upper()

    # Log message values in case of config clamping
    clamp_warning: tuple[int, int] | None = None

    if log_file:
        backup_count = app_config["options"]["log_backup_count"]
        clamped_backup_count = max(1, backup_count)

        # Set log values for deferred warning
        if clamped_backup_count != backup_count:
            clamp_warning = (clamped_backup_count, backup_count)

        handler = RotatingFileHandler(
            log_file,
            encoding="utf-8",
            maxBytes=app_config["options"]["log_max_bytes"],
            backupCount=clamped_backup_count,
        )
    else:
        handler = logging.StreamHandler()
        handler.setLevel(log_level)

    logging.basicConfig(
        level=logging.WARN,  # Default to WARN for root logger, avoid library noise
        handlers=[handler],
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logging.getLogger("exosphere").setLevel(log_level)

    # We don't raise an exception here, and defer this until now
    # because this function gets called during the "startup exceptions
    # are FATAL" phase of initialization, so we just log a warning.
    if clamp_warning is not None:
        logging.getLogger(__name__).warning(
            "log_backup_count must be at least 1! using %d instead of %r",
            *clamp_warning,
        )

    logging.getLogger(__name__).info("Logging initialized with level: %s", log_level)


def load_first_config(config: Configuration) -> bool:
    """
    Load the first configuration file found in either:

    - Environment variable EXOSPHERE_CONFIG_FILE (if set)
    - The list of predefined paths under fspaths.CONFIG_DIR.

    Those two are mutually exclusive, meaning if the environment variable
    is set, it will be used instead of the predefined paths.

    Brutally exits with non-zero status in case of issues beyond
    ENOENT and EISDIR.

    :param config: The configuration object to populate.

    :return: True if a configuration file was loaded, False otherwise.
    """

    env_config_file = os.environ.get("EXOSPHERE_CONFIG_FILE")
    env_config_path = os.environ.get("EXOSPHERE_CONFIG_PATH")

    if env_config_file:
        logger.info(
            "Using configuration file from environment variable: %s", env_config_file
        )
        paths = [Path(env_config_file)]
    elif env_config_path:
        logger.info(
            "Using configuration path from environment variable: %s", env_config_path
        )
        paths = config_paths(Path(env_config_path))
    else:
        logger.debug("Using default configuration paths")
        paths = config_paths(fspaths.CONFIG_DIR)

    for confpath in paths:
        logger.debug("Trying config file at %s", confpath)
        if not confpath.exists():
            continue

        logger.debug("Loading config file from %s", confpath)
        ext = confpath.suffix.removeprefix(".").lower()
        loader = KNOWN_LOADERS.get(ext)

        if not loader:
            logger.error("No working loaders for extension: %s, skipping.", ext)
            continue

        try:
            if config.from_file(filepath=str(confpath), loader=loader, silent=True):
                context.confpath = str(confpath)
                logger.info("Loaded config file from %s", confpath)
                return True
            else:
                logger.warning("Failed to load config file from %s", confpath)
        except Exception as e:
            # Abort brutally in case of non-standard load failure
            # Exception will contain the actual error message
            logger.error("Startup error: %s", e)
            sys.exit(1)

    return False


@atexit.register
def cleanup_connections() -> None:
    """
    Exit Handler to clean up SSH connections.

    Registered via atexit to ensure all SSH connections are properly
    cleaned up on program exit.

    Also handles shutting down the connection reaper thread used when
    SSH pipelining is enabled.

    In the event of abrupt horrors or early termination, this should
    do nothing harmful or unexpected.
    """

    logger.debug("Running exit handler for connections cleanup")

    # Stop the connection reaper thread first
    if context.reaper and context.reaper.is_running:
        logger.debug("Stopping connection reaper thread on exit")
        context.reaper.stop()

    # Close all remaining SSH connections and clear objects
    if context.inventory:
        logger.debug("Closing all SSH connections on exit")
        context.inventory.close_all(clear=True)


@atexit.register
def release_cache_lock() -> None:
    """
    Exit handler to release the cache file lock.

    Registered via atexit to ensure the exclusive cache lock is released
    on program exit. The OS frees the lock on process death regardless,
    but releasing explicitly is cleaner and removes the sidecar lock
    file swiftly.

    Safe to call when no lock was ever acquired.
    """
    logger.debug("Running exit handler for cache lock release")

    if context.cache_lock is not None and context.cache_lock.is_locked:
        logger.debug("Releasing cache lock on exit")
        context.cache_lock.release()


def main() -> None:
    """
    Program Entry Point
    """
    # Install rich traceback handler early
    install_rich_traceback(console=err_console, show_locals=False)

    # Fast-path calls to --version/-V to avoid unnecessary
    # initialization and potential lock contention
    if {"--version", "-V"} & set(sys.argv[1:]):
        cli.app()
        return

    # Ensure all required directories exist
    try:
        fspaths.ensure_dirs()
    except Exception as e:
        logger.error("Failed to create required directories: %s", e)
        sys.exit(1)

    # Load the first configuration file found
    if not load_first_config(app_config):
        logger.warning("No configuration file found. Using defaults.")

    logger.info("Configuration loaded from: %s", context.confpath)

    # Override configuration options with environment variables, if any
    app_config.from_env()

    # initialize logging and setup handlers depending on config
    log_file: str | None = app_config["options"].get("log_file")
    debug_mode: bool = app_config["options"].get("debug")

    try:
        if debug_mode:
            setup_logging(app_config["options"]["log_level"])
            logger.warning("Debug mode enabled! Logs may flood console!")
        else:
            setup_logging(app_config["options"]["log_level"], log_file)
    except Exception as e:
        print(f"FATAL: Startup Error setting up logging: {e}", file=sys.stderr)
        sys.exit(1)

    # Acquire exclusive lock on the cache file before inventory init.
    # Prevents concurrent instances from sharing the same cache file.
    # The lock is put on a sidecar .lock file, to avoid locking the
    # cache file itself.
    cache_file = app_config["options"]["cache_file"]
    context.cache_lock = FileLock(f"{cache_file}.lock")

    try:
        context.cache_lock.acquire(blocking=False)
    except Timeout:
        err_console.print(
            f"[red]FATAL:[/red] Another Exosphere instance is using this cache:\n"
            f"  {cache_file}\n"
            "Ensure no other instances with this configuration are running."
        )
        sys.exit(1)

    # Initialize the inventory
    try:
        context.inventory = Inventory(app_config)
    except Exception as e:
        logger.error("Startup Error loading inventory: %s", e)
        print(f"FATAL: Startup Error loading inventory: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize and start the connection reaper
    context.reaper = ConnectionReaper()
    context.reaper.start()

    # Launch the regular CLI or REPL
    if len(sys.argv) > 1:
        # Non-interactive errors should display help
        cli.app(help_on_error=True)
    else:
        cli.start_interactive()


if __name__ == "__main__":
    main()
