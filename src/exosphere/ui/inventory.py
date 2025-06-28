import logging

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

from exosphere import context
from exosphere.objects import Host, Update
from exosphere.ui.elements import ErrorScreen, ProgressScreen

logger = logging.getLogger("exosphere.ui.inventory")


class HostDetailsPanel(Screen):
    """Screen to display details of a selected host."""

    CSS_PATH = "style.tcss"

    def __init__(self, host: Host) -> None:
        super().__init__()
        self.host = host

    def compose(self) -> ComposeResult:
        """Compose the host details layout."""
        yield Vertical(
            Label(f"[b]Host[/b]: {self.host.name}", id="host-name"),
            Label(f"OS: {self.host.os}", id="host-os"),
            Label(f"IP Address: {self.host.ip}", id="host-ip"),
            Label(f"Port: {self.host.port}", id="host-port"),
            Label(f"Flavor: {self.host.flavor}", id="host-flavor"),
            Label(
                f"Operating System: {self.host.os} {self.host.flavor} {self.host.version}",
                id="host-version",
            ),
            Label(
                f"Description: {self.host.description or 'N/A'}", id="host-description"
            ),
            Label(
                f"Status: {'[green]Online[/green]' if self.host.online else '[red]Offline[/red]'}",
                id="host-online",
            ),
            Label(
                f"Last Updated: {self.host.last_refresh.strftime('%a %b %d %H:%M:%S %Y') if self.host.last_refresh else 'Never'}",
                id="host-last-updated",
            ),
            Label(
                f"Available Updates: {len(self.host.updates)}, {len(self.host.security_updates)} security",
                id="host-updates-count",
            ),
            Container(
                DataTable(id="host-updates-table", zebra_stripes=True),
                id="updates-table-container",
            ),
            Label("Press ESC to close", id="close-instruction"),
            classes="host-details",
        )

    def on_mount(self) -> None:
        """Populate the updates data table on mount."""
        self.title = f"Host Details: {self.host.name}"

        update_list = self.host.updates or []

        if not update_list:
            return

        updates_table = self.query_one(DataTable)
        updates_table.cursor_type = "row"  # Enable row selection

        # Define columns for the updates table
        updates_table.add_columns(
            "Package Update",
        )

        # Populate the updates table with available updates
        for update in update_list:
            updates_table.add_row(
                f"[red]{update.name}[/red]" if update.security else update.name,
                key=update.name,
            )

    def on_key(self, event) -> None:
        """Handle key presses to return to the inventory screen."""
        if event.key == "escape":
            self.dismiss()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the updates data table."""
        update_name = str(event.row_key.value)

        if not self.host:
            logger.error("Host is not initialized, cannot select update.")
            self.app.push_screen(ErrorScreen("Host is not initialized."))
            return

        update: Update = [u for u in self.host.updates if u.name == update_name][
            0
        ] or None

        if update is None:
            logger.error(f"Update not found for host '{self.host.name}'.")
            self.app.push_screen(
                ErrorScreen(f"Update not found for host '{self.host.name}'.")
            )
            return

        logger.debug(f"Selected update: {update.name}")
        self.app.push_screen(
            UpdateDetailsPanel(update),
        )


class UpdateDetailsPanel(Screen):
    """Screen to display details of a selected update."""

    CSS_PATH = "style.tcss"

    def __init__(self, update: Update) -> None:
        super().__init__()
        self.update = update

    def compose(self) -> ComposeResult:
        """Compose the update details layout."""
        yield Vertical(
            Label(f"[b]Update Details for[/b]: {self.update.name}", id="update-name"),
            Label(
                f"Current version: {self.update.current_version or 'N/A'}",
                id="update-current-version",
            ),
            Label(f"New version: {self.update.new_version}", id="update-new-version"),
            Label(f"Source:\n{self.update.source or 'N/A'}", id="update-source"),
            Label(
                f"Security update: {'[red]Yes[/red]' if self.update.security else 'No'}",
                id="update-security",
            ),
            Label("Press ESC to close", id="close-instruction"),
            classes="update-details",
        )

    def on_mount(self) -> None:
        """Set the title of the screen on mount."""
        self.title = f"Update Details: {self.update.name}"

    def on_key(self, event) -> None:
        """Handle key presses to return to the host details screen."""
        if event.key == "escape":
            self.dismiss()
            event.prevent_default()


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
            yield DataTable(id="inventory-table")

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        host_name = str(event.row_key.value)

        if not context.inventory:
            logger.error("Inventory is not initialized, cannot select row.")
            self.app.push_screen(ErrorScreen("Inventory is not initialized."))
            return

        host = context.inventory.get_host(host_name)

        if host is None:
            logger.error(f"Host '{host_name}' not found in inventory.")
            self.app.push_screen(
                ErrorScreen(f"Host '{host_name}' not found in inventory.")
            )
            return

        logger.debug(f"Selected host: {host}")
        self.app.push_screen(
            HostDetailsPanel(host),
        )

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
            sec_count: int = len(host.security_updates) if host.security_updates else 0

            if sec_count > 0:
                security_updates = f"[red]{sec_count}[/red]"
            else:
                security_updates = str(sec_count)

            table.add_row(
                host.name,
                host.os,
                host.flavor,
                host.version,
                len(host.updates),
                security_updates,
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
