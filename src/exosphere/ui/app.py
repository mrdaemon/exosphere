import logging

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, UILogHandler


class ExosphereUi(App):
    """The main application class for the Exosphere UI."""

    ui_log_handler: UILogHandler

    # Global Bindings - These are available in all modes,
    # unless overriden by a mode-specific binding.
    BINDINGS = [
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("i", "switch_mode('inventory')", "Inventory"),
        ("l", "switch_mode('logs')", "Logs"),
        ("q", "quit", "Quit"),
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
        # Initialize logging handler for logs panel
        self.ui_log_handler = UILogHandler()
        self.ui_log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logging.getLogger("exosphere").addHandler(self.ui_log_handler)

        # Set the default mode to the dashboard
        self.switch_mode("dashboard")
