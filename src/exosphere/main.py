import logging

from exosphere import cli
from exosphere.inventory import Configuration


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
    logging.getLogger().setLevel(log_level)


def main() -> None:
    """
    Program Entry Point
    """

    # We're running on defaults for now
    # FIXME: Resolve when we implement reading the config file
    config = Configuration()
    setup_logging(config["options"]["log_level"])

    cli.app()


if __name__ == "__main__":
    main()
