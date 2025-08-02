"""
Inventory Screen Module
"""

import logging
import re
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

from exosphere import context
from exosphere.objects import Host, Update
from exosphere.ui.context import screenflags
from exosphere.ui.elements import ErrorScreen, ProgressScreen
from exosphere.ui.messages import HostStatusChanged

logger = logging.getLogger("exosphere.ui.inventory")


class HostDetailsPanel(Screen):
    """Screen to display details of a selected host."""

    CSS_PATH = "style.tcss"

    def __init__(self, host: Host) -> None:
        super().__init__()
        self.host = host

    def compose(self) -> ComposeResult:
        """Compose the host details layout."""

        sec_count: int = (
            len(self.host.security_updates) if self.host.security_updates else 0
        )
        security_updates: str = (
            f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
        )

        platform: str

        if not self.host.flavor or not self.host.version:
            platform = "(Undiscovered)"
        elif self.host.os == self.host.flavor:
            platform = f"{self.host.os} {self.host.version}"
        else:
            platform = f"{self.host.os} ({self.host.flavor} {self.host.version})"

        yield Vertical(
            Label(f"[i]Host:[/i]\n  {self.host.name}", id="host-name"),
            Label(f"[i]IP Address:[/i]\n  {self.host.ip}", id="host-ip"),
            Label(f"[i]Port:[/i]\n  {self.host.port}", id="host-port"),
            Label(
                f"[i]Operating System:[/i]\n  {platform}",
                id="host-version",
            ),
            Label(
                f"[i]Description:[/i]\n  {self.host.description or 'N/A'}",
                id="host-description",
            ),
            Label(
                f"[i]Status:[/i]\n  {'[green]Online[/green]' if self.host.online else '[red]Offline[/red]'}",
                id="host-online",
            ),
            Label(
                f"[i]Last Updated:[/i]\n  {self.host.last_refresh.strftime('%a %b %d %H:%M:%S %Y') if self.host.last_refresh else 'Never'}",
                id="host-last-updated",
            ),
            Label(
                f"[i]Stale:[/i]\n  {'[red]Yes[/red] - Consider refreshing' if self.host.is_stale else 'No'}",
                id="host-stale",
            ),
            Label(
                f"[i]Available Updates:[/i]\n  {len(self.host.updates)} updates, {security_updates} security",
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
                f"[red]{update.name}[/red]" if update.security else update.name
            )

    def on_key(self, event) -> None:
        """Handle key presses to return to the inventory screen."""
        if event.key == "escape":
            self.dismiss()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the updates data table."""

        # Retrieve the selected row by automatically generated key
        table = self.query_one(DataTable)
        row_data = table.get_row(event.row_key)

        # Extract the update name, removing Rich markup if present
        update_display_name = str(row_data[0])  # First column
        update_name = re.sub(r"\[/?[^\]]*\]", "", update_display_name)

        logger.debug(f"Selected update name: {update_name}")

        if not self.host:
            logger.error("Host is not initialized, cannot select update.")
            self.app.push_screen(ErrorScreen("Host is not initialized."))
            return

        update: Update | None = next(
            (u for u in self.host.updates if u.name == update_name), None
        )

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
            Label(f"[i]Package:[/i] {self.update.name}", id="update-name"),
            Label("[i]Version Change:[/i]", id="update-version-change"),
            Label(
                f"  [yellow]{self.update.current_version or '(NEW)'}[/yellow] → [green]{self.update.new_version}[/green]",
                id="update-version",
            ),
            Label(
                f"[i]Source[/i]: {self.update.source or '(N/A)'}", id="update-source"
            ),
            Label(
                f"[i]Security update[/i]: {'[red]Yes[/red]' if self.update.security else 'No'}",
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


class InventoryScreen(Screen):
    """Screen for the inventory."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("ctrl+r", "refresh_updates_all", "Refresh Updates"),
        ("ctrl+x", "sync_repos_all", "Sync Repos"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the inventory layout."""
        yield Header()

        hosts = getattr(context.inventory, "hosts", []) or []

        if not hosts:
            with Vertical():
                with Container(id="empty-container"):
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

        # Retrieve the selected row by automatically generated key
        table = self.query_one(DataTable)
        row_data = table.get_row(event.row_key)

        host_name = str(row_data[0])  # First column is the host name

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

    def on_screen_resume(self) -> None:
        """Refresh the data table if the screen is dirty"""
        if screenflags.is_screen_dirty("inventory"):
            logger.debug("Inventory screen is dirty, refreshing rows.")
            self.refresh_rows()
            screenflags.flag_screen_clean("inventory")

    def refresh_rows(self, task: str | None = None) -> None:
        """Repopulate all rows in the data table from the inventory."""

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

        table = self.query_one(DataTable)

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

    def action_sync_repos_all(self) -> None:
        """Action to sync repositories for all hosts."""

        self._run_task(
            taskname="sync_repos",
            message="Syncing repositories for all hosts.\nThis may take a long time!",
            no_hosts_message="No hosts available to sync repositories.",
            save_state=False,  # Syncing repos does not affect state
            callback=lambda _: None,  # No need to flag screens dirty
        )

    def _populate_table(self, table: DataTable, hosts: list[Host]):
        """Populate given table with host data"""

        def maybe_undiscovered(value: str | None) -> str:
            """Format as undiscovered if None or empty"""
            return value if value else "[dim](undiscovered)[/dim]"

        for host in hosts:
            sec_count: int = len(host.security_updates) if host.security_updates else 0
            upd_count: int = len(host.updates) if host.updates else 0

            security_updates = (
                f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
            )
            updates = str(upd_count)

            if host.is_stale:
                updates += "[dim] *[/dim]"
                security_updates += "[dim] *[/dim]"

            status_str = (
                "[green]Online[/green]" if host.online else "[red]Offline[/red]"
            )

            table.add_row(
                host.name,
                maybe_undiscovered(host.os),
                maybe_undiscovered(host.flavor),
                maybe_undiscovered(host.version),
                updates,
                security_updates,
                status_str,
            )

    def _run_task(
        self,
        taskname: str,
        message: str,
        no_hosts_message: str,
        save_state: bool = True,
        callback: Callable | None = None,
    ) -> None:
        """
        Dispatch a task to all hosts in the inventory.

        Note: If you modify the callback via parameter, you are on your
        own to refresh the data table after the task is completed.

        :param taskname: Name of the task to run.
        :param message: Message to display in the progress screen.
        :param no_hosts_message: Message to display if no hosts are available.
        :param save_state: Whether to save the state after running the task.
        :param callback: Optional callback function to execute after the task.
                         Defaults implicitly to self.refresh_rows().
        """

        def send_message(_):
            """Send message to flag other screens as dirty"""
            logger.debug("Task %s completed, sending status change message.", taskname)
            self.post_message(HostStatusChanged("inventory"))
            self.refresh_rows(taskname)

        inventory = context.inventory

        if inventory is None:
            logger.error("Inventory is not initialized, cannot run tasks.")
            self.app.push_screen(
                ErrorScreen("Inventory is not initialized, cannot run tasks.")
            )
            return

        hosts = inventory.hosts if inventory else []

        if not hosts:
            logger.warning("No hosts available to run task '%s'.", taskname)
            self.app.push_screen(ErrorScreen(no_hosts_message))
            return

        self.app.push_screen(
            ProgressScreen(
                message=message,
                hosts=hosts,
                taskname=taskname,
                save=save_state,
            ),
            callback or send_message,
        )
