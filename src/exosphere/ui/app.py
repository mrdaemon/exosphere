"""
Exosphere TUI Application Module

This module defines the main application class for the Exosphere
Text User Interface (TUI) application. It manages the overall
application state, handles global key bindings, and manages
the modal screen state for different UI components.

Acts as the entrypoint for the UI component of Exosphere.
"""

import logging

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from exosphere.ui.context import screenflags
from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, RichLogFormatter, UILogHandler
from exosphere.ui.messages import HostStatusChanged


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

    async def on_host_status_changed(self, message: HostStatusChanged) -> None:
        """
        Handle host status change messages to refresh screens.
        """
        logging.debug("Received host status change message, refreshing screens.")
        # Refresh all screens that are registered
        if message.current_screen not in screenflags.registered_screens:
            logging.warning(
                f"Received host status change from unregistered screen: {message.current_screen}"
            )

        # Flag all screens as dirty except the one who sent the message
        screenflags.flag_screen_dirty_except(message.current_screen)

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
