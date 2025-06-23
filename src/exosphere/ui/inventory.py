from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder


class InventoryScreen(Screen):
    """Screen for the inventory."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("^d", "discover_all_hosts", "Discover Hosts"),
        ("^r", "refresh_updates_all", "Refresh Updates"),
        ("^x", "refresh_updates_catalog_all", "Refresh Catalog"),
        ("^p", "ping_all_hosts", "Ping Hosts"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the inventory layout."""
        yield Header()
        yield Placeholder(name="inventory_content", label="Inventory Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the inventory."""
        self.title = "Exosphere"
        self.sub_title = "Inventory Management"
