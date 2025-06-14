from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen


class ExosphereUi(App):
    """The main application class for the Exosphere UI."""

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
        """Compose the application layout."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.switch_mode("dashboard")
