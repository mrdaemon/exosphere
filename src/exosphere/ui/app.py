import logging

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, UILogHandler


class ExosphereUi(App):
    """The main application class for the Exosphere UI."""

    ui_log_handler: UILogHandler | None

    # Global Bindings - These are available in all modes,
    # unless overriden by a mode-specific binding.
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

    def compose(self) -> ComposeResult:
        """Compose the common application layout."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI Log handler and set the default mode."""
        # Initialize logging handler for logs panel
        self.ui_log_handler = UILogHandler()
        self.ui_log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
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
