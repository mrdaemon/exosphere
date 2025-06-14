from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder


class DashboardScreen(Screen):
    """Screen for the dashboard."""

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()
        yield Placeholder(name="dashboard_content", label="Dashboard Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"


class InventoryScreen(Screen):
    """Screen for the inventory."""

    def compose(self) -> ComposeResult:
        """Compose the inventory layout."""
        yield Header()
        yield Placeholder(name="inventory_content", label="Inventory Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the inventory."""
        self.title = "Exosphere"
        self.sub_title = "Inventory Management"


class LogsScreen(Screen):
    """Screen for the logs."""

    def compose(self) -> ComposeResult:
        """Compose the logs layout."""
        yield Header()
        yield Placeholder(name="logs_content", label="Logs Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the logs."""
        self.title = "Exosphere"
        self.sub_title = "Logs Viewer"


class ExosphereUi(App):
    """The main application class for the Exosphere UI."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("i", "switch_mode('inventory')", "Inventory"),
        ("l", "switch_mode('logs')", "Logs"),
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
