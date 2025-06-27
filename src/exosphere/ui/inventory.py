import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

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

        hosts = getattr(context.inventory, "hosts", []) or []

        if not hosts:
            yield Label("No hosts in inventory.", classes="empty-message")
        else:
            yield DataTable()

        yield Footer()

    def on_mount(self) -> None:
        """Populate the data table on mount"""
        self.title = "Exosphere"
        self.sub_title = "Inventory Management"

        hosts = context.inventory.hosts if context.inventory else []

        if not hosts:
            logger.warning("Inventory is empty.")
            return

        table = self.query_one(DataTable)

        COLUMNS = (
            "Host",
            "Description",
            "OS",
            "Flavor",
            "Version",
            "Updates",
            "Security",
            "Status",
        )

        table.add_columns(*COLUMNS)

        for host in hosts:
            table.add_row(
                host.name,
                host.description or "server",
                host.os,
                host.flavor,
                host.version,
                len(host.updates),
                len(host.security_updates),
                "[green]Online[/green]" if host.online else "[red]Offline[/red]",
            )

    def _run_task(self, taskname: str, message: str, no_hosts_message: str) -> None:
        hosts = context.inventory.hosts if context.inventory else []

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
