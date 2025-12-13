"""
Pipelining module for Exosphere

This module contains classes and functions related to ssh pipelining
within Exosphere.
"""

import logging
import time
from threading import Event, Thread

from exosphere import app_config, context
from exosphere.inventory import Inventory

# Minimum recommended reaper interval in seconds
MIN_REAPER_INTERVAL = 120


class ConnectionReaper:
    """
    Manages the idle connection reaper thread.

    Background/Daemon thread that periodically checks the last used
    time of connections for each host in the inventory against the
    ssh_pipelining_lifetime setting.

    Idle connections older than that value are closed to free up
    resources.

    Only runs when ssh_pipelining is enabled.
    """

    def __init__(self) -> None:
        """
        Initialize the connection reaper thread.
        """
        self.logger = logging.getLogger(__name__)

        self._inventory: Inventory | None = context.inventory
        self._thread: Thread | None = None
        self._stop_event = Event()

        self.max_lifetime: int = app_config["options"]["ssh_pipelining_lifetime"]
        self.check_interval = app_config["options"]["ssh_pipelining_reap_interval"]

    @property
    def is_running(self) -> bool:
        """
        Check if the reaper thread is currently running.

        :return: True if the reaper thread is active, False otherwise.
        """
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """
        Start the Reaper thread in background.

        Logs a warning does nothing if the thread is already running.
        Silently returns if ssh pipelining is disabled.
        """

        if not self._inventory:
            self.logger.error(
                "Cannot start connection reaper: inventory not initialized!"
            )
            return

        if not app_config["options"]["ssh_pipelining"]:
            self.logger.debug("SSH pipelining disabled, not starting reaper thread")
            return

        if self._thread is not None and self._thread.is_alive():
            self.logger.warning(
                "Not starting connection reaper thread: already running!"
            )
            return

        # Sanity check on lifetime, as very low values may cause issues
        if self.max_lifetime < MIN_REAPER_INTERVAL:
            self.logger.warning(
                f"ssh_pipelining_lifetime ({self.max_lifetime}s) is very short! "
                f"Long-running commands may be interrupted. Recommended: >= {MIN_REAPER_INTERVAL}s"
            )

        self.logger.info("Starting connection reaper thread")
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="ConnectionReaper")
        self._thread.start()

    def stop(self) -> None:
        """
        Stop the reaper thread gracefully.

        Signals the thread to stop and waits for it to complete.
        Times out after 5 seconds to avoid blocking.
        """
        if self._thread is None or not self._thread.is_alive():
            self.logger.debug("Reaper thread stop requested, but thread not running!")
            return

        self.logger.info("Stopping connection reaper thread")
        self._stop_event.set()
        self._thread.join(timeout=5.0)

    def _run(self) -> None:
        """
        Main loop for the reaper thread.

        Continuously checks for idle connections and closes them
        until the stop event is set.
        """

        while not self._stop_event.is_set():
            self.close_idle_connections()
            self._stop_event.wait(timeout=self.check_interval)

        self.logger.debug("Connection reaper thread received stop signal")

    def close_idle_connections(self) -> None:
        """
        Check all hosts and close connections that have been idle too long.

        A connection is considered idle if it hasn't been used for longer
        than ssh_pipelining_lifetime seconds.
        """

        assert self._inventory is not None
        if not self._inventory.hosts:
            self.logger.debug(
                "Inventory has no hosts, skipping idle connection reaping"
            )
            return

        now = time.time()
        reaped_count = 0

        for host in self._inventory.hosts:
            if host.connection_last_used is None:
                continue

            # Check idle/age time
            idle_time = now - host.connection_last_used
            if idle_time > self.max_lifetime:
                self.logger.debug(
                    "Closing idle connection to %s (idle for %.1f seconds)",
                    host.name,
                    idle_time,
                )
                try:
                    host.close(clear=False)
                    reaped_count += 1
                except Exception as e:
                    self.logger.error(
                        "Error closing connection to %s: %s",
                        host.name,
                        e,
                        exc_info=True,
                    )

        if reaped_count > 0:
            self.logger.info("Closed %d idle connection(s)", reaped_count)
