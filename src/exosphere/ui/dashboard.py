from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder


class DashboardScreen(Screen):
    """Screen for the dashboard."""

    BINDINGS = [
        ("p", "ping_all_hosts", "Ping All"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()
        yield Placeholder(name="dashboard_content", label="Dashboard Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"
