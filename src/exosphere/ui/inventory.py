import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder

from exosphere import context
from exosphere.ui.elements import ErrorScreen, ProgressScreen

logger = logging.getLogger("exosphere.ui.inventory")


class InventoryScreen(Screen):
    """Screen for the inventory."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("ctrl+r", "refresh_updates_all", "Refresh Updates"),
        ("ctrl+x", "refresh_updates_catalog_all", "Refresh Catalog"),
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

    def _run_task(self, taskname: str, message: str, no_hosts_message: str) -> None:
        inventory = context.inventory
        hosts = inventory.hosts if inventory else []

        if not hosts:
            logger.warning(f"No hosts available to run task '{taskname}'.")
            self.app.push_screen(ErrorScreen(no_hosts_message))
            return

        self.app.push_screen(
            ProgressScreen(
                message=message,
                hosts=hosts,
                taskname=taskname,
            )
        )

    def action_refresh_updates_all(self) -> None:
        """Action to refresh updates for all hosts."""

        self._run_task(
            taskname="refresh_updates",
            message="Refreshing updates for all hosts...",
            no_hosts_message="No hosts available to refresh updates.",
        )

    def action_refresh_updates_catalog_all(self) -> None:
        """Action to refresh updates and package catalog for all hosts."""

        self._run_task(
            taskname="refresh_catalog",
            message="Refreshing package catalog for all hosts...\nThis may take a long time!",
            no_hosts_message="No hosts available to refresh package catalog.",
        )
