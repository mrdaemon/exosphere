import logging
from datetime import datetime, timezone

from exosphere.data import HostState
from exosphere.objects import Host

logger = logging.getLogger(__name__)


def migrate_from_host(host: Host) -> HostState:
    """
    Migrate a Host object to a HostState object for serialization.
    Ensures any cache formats from version earlier than 2.2.0 are
    correctly upgraded to the current HostState format.

    :param host: Host instance to migrate from
    :return: HostState instance
    """

    logger.info("Migrating Host state from legacy Host object for host %s", host.name)

    # Ensure supported member is set, defaulting to True if missing
    if not hasattr(host, "supported"):
        logger.debug(
            "Setting missing supported attribute to True for host %s", host.name
        )
        host.supported = True

    # Ensure last_refresh is timezone-aware in UTC
    # Much earlier versions of Exosphere stored it as naive datetimes.
    if hasattr(host, "last_refresh") and host.last_refresh is not None:
        if host.last_refresh.tzinfo is None:
            logger.debug(
                "Converting timezone-naive last_refresh datetime to UTC for host %s",
                host.name,
            )
            local_timestamp = host.last_refresh.timestamp()
            host.last_refresh = datetime.fromtimestamp(local_timestamp, tz=timezone.utc)

    return HostState(
        os=host.os,
        version=host.version,
        flavor=host.flavor,
        package_manager=host.package_manager,
        supported=host.supported,
        online=host.online,
        updates=tuple(host.updates),
        last_refresh=host.last_refresh,
    )
