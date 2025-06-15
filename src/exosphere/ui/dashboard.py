import logging

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from exosphere import context


class HostGrid(Grid):
    """Grid to display hosts in the dashboard."""

    def compose(self) -> ComposeResult:
        """Compose the grid layout."""
        inventory = context.inventory

        hosts = inventory.hosts if inventory else []
        for host in hosts:
            logging.getLogger("exosphere.ui").debug(f"Adding host: {host.name}")
            if host.online:
                classes = "host-box online"
            else:
                classes = "host-box offline"

            yield Static(host.name, classes=classes)


class DashboardScreen(Screen):
    """Screen for the dashboard."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("^p", "ping_all_hosts", "Ping All"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()
        yield HostGrid(classes="centered-grid")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"
