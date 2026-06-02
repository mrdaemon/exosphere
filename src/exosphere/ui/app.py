"""
Exosphere TUI Application Module

This module defines the main application class for the Exosphere
Text User Interface (TUI) application. It manages the overall
application state, handles global key bindings, and manages
the modal screen state for different UI components.

Acts as the entrypoint for the UI component of Exosphere.
"""

import logging
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from exosphere import context
from exosphere.inventory import HostOperation
from exosphere.objects import Host
from exosphere.ui.context import screenflags
from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.elements import DataScreen, ErrorScreen, ProgressScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, RichLogFormatter, UILogHandler


class ExosphereUi(App):
    """
    The main application class for the Exosphere UI.

    This class manages a handful of things, including the overall
    application state, the global key bindings and modes,
    as well as the status bar setup and composition.

    Since it manages the modal screen state, it is also responsible
    for tracking which screens need refreshed when the shared data
    changes via the message system.
    """

    ui_log_handler: UILogHandler | None

    # Global Bindings - These are available in all modes,
    # unless overridden by a mode-specific binding.
    BINDINGS = [
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("i", "switch_mode('inventory')", "Inventory"),
        ("l", "switch_mode('logs')", "Logs"),
        ("^q", "quit", "Quit"),
    ]

    MODES = {
        "dashboard": DashboardScreen,
        "inventory": InventoryScreen,
        "logs": LogsScreen,
    }

    def run_host_task(
        self,
        operation: HostOperation,
        hosts: list[Host] | None = None,
        *,
        message: str,
        no_hosts_message: str,
        save_state: bool = True,
        callback: Callable | None = None,
    ) -> None:
        """
        Dispatch a host operation off the UI thread, refresh screens.

        Handles pushing a :class:`ProgressScreen` to run the the
        ``operation`` on the given hosts (or all hosts, when unspecified).

        On completion, unless a custom ``callback`` is specified, runs
        the default post-task bookkeeping:

        - Refresh the currently visible data screen in place (if active)
        - Flag all other registered data screens dirty so they redraw on
          resume.

        This is intended to be called from within the TUI, and is the
        canonical way to run hosts tasks from UI threads.

        :param operation: The :class:`HostOperation` to run.
        :param hosts: Hosts to target, defaults to all hosts.
        :param message: Message to display in the progress screen.
        :param no_hosts_message: Message shown if no hosts are available.
        :param save_state: Whether to save state after the task completes.
        :param callback: Optional callback to run after the task instead of
                         the default refresh bookkeeping.
        """
        inventory = context.inventory
        if inventory is None:
            self.push_screen(
                ErrorScreen("Inventory is not initialized, cannot run tasks.")
            )
            return

        target_hosts = hosts if hosts is not None else inventory.hosts
        if not target_hosts:
            logging.warning("No hosts available to run task '%s'.", operation.value)
            self.push_screen(ErrorScreen(no_hosts_message))
            return

        self.push_screen(
            ProgressScreen(message, target_hosts, operation, save_state),
            callback or self._after_task(operation),
        )

    def _after_task(self, operation: HostOperation) -> Callable:
        """
        Helper function that generates the default callback for the
        task runner in the TUI, which handles the bookkeeping
        described above in :meth:`run_host_task`.
        """

        def callback(_) -> None:
            screen = self.screen

            if isinstance(screen, DataScreen):
                name = screen.get_screen_name()
                if name in screenflags.registered_screens:
                    logging.debug(
                        "Task %s done; refreshing active screen %s, flagging others.",
                        operation.value,
                        name,
                    )
                    # Task was dispatched from this screen, skip notification
                    screen.refresh_data_after_task(operation.value, notify=False)
                    screenflags.flag_screen_dirty_except(name)
                    return

            logging.debug(
                "Task %s done from non-data screen; flagging all data screens.",
                operation.value,
            )
            screenflags.flag_screen_dirty(*screenflags.registered_screens)

        return callback

    def compose(self) -> ComposeResult:
        """Compose the common application layout."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI Log handler and set the default mode."""

        # Initialize the screen flags registry
        # This list should contain all screens that display data from
        # exosphere.objects or exosphere.inventory
        screenflags.register_screens("dashboard", "inventory")

        # Initialize logging handler for logs panel
        self.ui_log_handler = UILogHandler()
        self.ui_log_handler.setFormatter(RichLogFormatter(datefmt="%H:%M:%S"))
        logging.getLogger("exosphere").addHandler(self.ui_log_handler)

        # Set the default mode to the dashboard
        self.switch_mode("dashboard")

    def on_unmount(self) -> None:
        """Clean up the UI log handler when the app is unmounted."""
        if self.ui_log_handler is not None:
            logging.getLogger("exosphere").removeHandler(self.ui_log_handler)
            self.ui_log_handler.close()
            self.ui_log_handler = None

        logging.debug("UI log handler cleaned up on unmount.")

    def action_none(self) -> None:
        """
        No-op action for disabled bindings.

        This exists solely to provide something to link to for key
        bindings that are overridden in local modal screens, usually
        with the express intent to hide them.

        I genuinely do not understand the reactive part of bindings
        across modal screens in Textual, so this is the least
        horrifying solution I could think of.
        """
        pass
