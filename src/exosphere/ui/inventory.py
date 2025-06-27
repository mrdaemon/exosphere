import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

from exosphere import context
from exosphere.objects import Host
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
        table.cursor_type = "row"
        table.zebra_stripes = True

        COLUMNS = (
            "Host",
            "OS",
            "Flavor",
            "Version",
            "Updates",
            "Security",
            "Status",
        )

        table.add_columns(*COLUMNS)

        self._populate_table(table, hosts)

    def refresh_rows(self, task: str | None = None) -> None:
        """Repopulate all rows in the data table from the inventory."""
        table = self.query_one(DataTable)

        if not context.inventory:
            logger.error("Inventory is not initialized, cannot update rows.")
            self.app.push_screen(
                ErrorScreen("Inventory is not initialized, failed to refresh table")
            )
            return

        hosts = context.inventory.hosts if context.inventory else []

        if not hosts:
            logger.warning("No hosts available to update rows.")
            self.app.push_screen(ErrorScreen("No hosts available to update rows."))
            return

        # Clear table but keep columns
        table.clear(columns=False)

        # Repopulate
        self._populate_table(table, hosts)

        if task:
            logger.debug("Updated data table due to task: %s", task)
        else:
            logger.debug("Updated data table.")

        self.app.notify("Table data refreshed successfully.", title="Refresh Complete")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table"""

        if context.inventory is None or not context.inventory.hosts:
            logger.error("Inventory is not initialized, cannot select row.")
            self.app.push_screen(ErrorScreen("Inventory is not initialized."))
            return

        host_name = str(event.row_key.value)
        host = context.inventory.get_host(host_name)

        if host is None:
            logger.error(f"Host '{host_name}' not found in inventory.")
            self.app.push_screen(ErrorScreen(f"Host '{host_name}' not found."))
            return

        logger.debug(f"Selected host: {host}")
        # Here I would push the details screen but it doesn't exist yet.

    def action_refresh_updates_all(self) -> None:
        """Action to refresh updates for all hosts."""

        self._run_task(
            taskname="refresh_updates",
            message="Refreshing updates for all hosts...",
            no_hosts_message="No hosts available to refresh updates.",
            save_state=True,
        )

    def action_refresh_updates_catalog_all(self) -> None:
        """Action to refresh updates and package catalog for all hosts."""

        self._run_task(
            taskname="refresh_catalog",
            message="Refreshing package catalog for all hosts...\nThis may take a long time!",
            no_hosts_message="No hosts available to refresh package catalog.",
            save_state=False,  # Refreshing catalog does not affect state
        )

    def _populate_table(self, table: DataTable, hosts: list[Host]):
        """Populate given table with host data"""
        for host in hosts:
            table.add_row(
                host.name,
                host.os,
                host.flavor,
                host.version,
                len(host.updates),
                len(host.security_updates),
                "[green]Online[/green]" if host.online else "[red]Offline[/red]",
                key=host.name,
            )

    def _run_task(
        self,
        taskname: str,
        message: str,
        no_hosts_message: str,
        save_state: bool = True,
    ) -> None:
        """
        Dispatch a task to all hosts in the inventory.
        """
        inventory = context.inventory

        if inventory is None:
            logger.error("Inventory is not initialized, cannot run tasks.")
            self.app.push_screen(
                ErrorScreen("Inventory is not initialized, cannot run tasks.")
            )
            return

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
                save=save_state,
            ),
            self.refresh_rows,
        )
