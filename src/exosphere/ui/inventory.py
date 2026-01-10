"""
Inventory Screen Module
"""

import logging
import re
from enum import StrEnum

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Grid, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, ListItem, ListView

from exosphere import context
from exosphere.objects import Host, Update
from exosphere.ui.context import screenflags
from exosphere.ui.elements import ErrorScreen, TaskRunnerScreen

logger = logging.getLogger("exosphere.ui.inventory")


class FilterMode(StrEnum):
    """
    Filter modes for inventory FilterScreen
    """

    NONE = "All Hosts"
    UPDATES_ONLY = "Updates"
    SECURITY_ONLY = "Security Updates"


class FilterScreen(Screen):
    """
    Screen for filtering hosts in the inventory view

    Presents a UI for filtering hosts in the inventory view based on
    various criteria.

    Returns the selected FilterMode enum value on selection or None
    on dismissal.
    """

    CSS_PATH = "style.tcss"

    def compose(self) -> ComposeResult:
        yield Center(
            Container(
                Label("Filter Inventory View", id="filter-title"),
                ListView(
                    ListItem(Label("Show [u]A[/u]ll"), id="filter-none"),
                    ListItem(Label("[u]U[/u]pdates Only"), id="filter-updates"),
                    ListItem(
                        Label("[u]S[/u]ecurity Updates Only"), id="filter-security"
                    ),
                    id="filter-list",
                    initial_index=0,
                ),
                Label(
                    "[dim]↑/↓, Enter to select, ESC to cancel[/dim]",
                    id="filter-help",
                ),
                classes="filter-message",
            ),
            id="filter-center",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """
        Handle list item selection
        Map to FilterMode enum and dismiss screen with value
        """
        item_id = event.item.id

        # If something went terribly wrong, abort early.
        if not item_id:
            logger.warning("Selected item has no ID, cannot process filter selection!")
            return

        filter_map = {
            "filter-none": FilterMode.NONE,
            "filter-updates": FilterMode.UPDATES_ONLY,
            "filter-security": FilterMode.SECURITY_ONLY,
        }

        selected_filter = filter_map.get(item_id)
        self.dismiss(selected_filter)
        event.stop()

    def on_key(self, event: Key) -> None:
        """
        Handle window key events for quick select and exit
        """
        match event.key:
            case "escape":
                self.dismiss(None)
            case "a" | "A":
                self.dismiss(FilterMode.NONE)
            case "u" | "U":
                self.dismiss(FilterMode.UPDATES_ONLY)
            case "s" | "S":
                self.dismiss(FilterMode.SECURITY_ONLY)


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
            f"[$text-warning]{sec_count}[/]" if sec_count > 0 else str(sec_count)
        )

        platform: str

        if not self.host.supported:
            platform = f"{self.host.os} [$text-warning](Unsupported)[/]"
        elif not self.host.flavor or not self.host.version:
            platform = "(Undiscovered)"
        elif self.host.os == self.host.flavor:
            platform = f"{self.host.os} {self.host.version}"
        else:
            platform = f"{self.host.os} ({self.host.flavor} {self.host.version})"

        # Base components that are always shown
        components = [
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
                f"[i]Status:[/i]\n  {'[$text-success]Online[/]' if self.host.online else '[$text-error]Offline[/]'}",
                id="host-online",
            ),
        ]

        # Only show update-related information for supported hosts
        if self.host.supported:
            components += [
                Label(
                    f"[i]Last Refreshed:[/i]\n  {self.host.last_refresh.astimezone().strftime('%a %b %d %H:%M:%S %Y') if self.host.last_refresh else 'Never'}",
                    id="host-last-updated",
                ),
                Label(
                    f"[i]Stale:[/i]\n  {'[$text-warning]Yes[/] - Consider refreshing' if self.host.is_stale else 'No'}",
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
            ]

        # Instructions and help
        components.append(Label("Press ESC to close", id="close-instruction"))

        yield Vertical(*components, classes="host-details")

    def on_mount(self) -> None:
        """Populate the updates data table on mount."""
        self.title = f"Host Details: {self.host.name}"

        # Only populate update table for supported hosts
        if not self.host.supported:
            return

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

    def on_key(self, event: Key) -> None:
        """Handle key presses to return to the inventory screen."""
        if event.key == "escape":
            self.dismiss()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the updates data table."""

        # Retrieve the selected row by automatically generated key
        table = self.query_one(DataTable)
        row_data = table.get_row(event.row_key)

        # Extract the update name, removing Rich markup if present
        update_display_name = row_data[0]  # First column
        update_name = re.sub(r"\[/?[^\]]*\]", "", update_display_name)

        logger.debug("Selected update name: %s", update_name)

        if not self.host:
            logger.error("Host is not initialized, cannot select update.")
            self.app.push_screen(ErrorScreen("Host is not initialized."))
            return

        update: Update | None = next(
            (u for u in self.host.updates if u.name == update_name), None
        )

        if update is None:
            logger.error("Update not found for host '%s'.", self.host.name)
            self.app.push_screen(
                ErrorScreen(f"Update not found for host '{self.host.name}'.")
            )
            return

        logger.debug("Selected update: %s", update.name)
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
                f"  [$text-warning]{self.update.current_version or '(NEW)'}[/] → [$text-success]{self.update.new_version}[/]",
                id="update-version",
            ),
            Label(
                f"[i]Source[/i]: {self.update.source or '(N/A)'}", id="update-source"
            ),
            Label(
                f"[i]Security update[/i]: {'[$text-error]Yes[/]' if self.update.security else 'No'}",
                id="update-security",
            ),
            Label("Press ESC to close", id="close-instruction"),
            classes="update-details",
        )

    def on_mount(self) -> None:
        """Set the title of the screen on mount."""
        self.title = f"Update Details: {self.update.name}"

    def on_key(self, event: Key) -> None:
        """Handle key presses to return to the host details screen."""
        if event.key == "escape":
            self.dismiss()


class InventoryScreen(TaskRunnerScreen):
    """Screen for the inventory."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        Binding("i", "app.none", show=False),
        ("ctrl+r", "refresh_updates_all", "Refresh Updates"),
        ("ctrl+x", "sync_and_refresh_all", "Sync & Refresh"),
        ("ctrl+f", "filter_view", "Filter"),
    ]

    def __init__(self) -> None:
        """Initialize the inventory screen."""
        super().__init__()
        self.current_filter: FilterMode = FilterMode.NONE

    def compose(self) -> ComposeResult:
        """Compose the inventory layout."""
        yield Header()

        hosts = getattr(context.inventory, "hosts", []) or []

        if not hosts:
            with Vertical():
                with Container(id="empty-container"):
                    yield Label("No hosts in inventory.", classes="empty-message")
        else:
            with Vertical(id="inventory-container"):
                yield DataTable(id="inventory-table")
                with Grid(id="inventory-info-bar", classes="inventory-info"):
                    yield Label("", id="inventory-spacer")
                    yield Label("", id="inventory-filter-label")
                    yield Label("│", id="inventory-separator")
                    yield Label("* indicates stale data", id="inventory-stale-label")

        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Populate the data table on mount"""
        self.title = "Exosphere"
        self.sub_title = "Inventory Management"

        # On mount, the filter should be All Hosts
        hosts = self.get_filtered_hosts()

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
        self._update_status_bar()

    def get_screen_name(self) -> str:
        """Return screen identifier."""
        return "inventory"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""

        # Retrieve the selected row by automatically generated key
        table = self.query_one(DataTable)
        row_data = table.get_row(event.row_key)

        host_name = row_data[0]  # First column is the host name

        if not context.inventory:
            logger.error("Inventory is not initialized, cannot select row.")
            self.app.push_screen(ErrorScreen("Inventory is not initialized."))
            return

        host = context.inventory.get_host(host_name)

        if host is None:
            logger.error("Host '%s' not found in inventory.", host_name)
            self.app.push_screen(
                ErrorScreen(f"Host '{host_name}' not found in inventory.")
            )
            return

        logger.debug("Selected host: %s", host)
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

        # Get filtered hosts based on current filter mode
        hosts = self.get_filtered_hosts()

        if not hosts:
            logger.warning("No hosts match the current filter.")
            # Still show empty table rather than error
            table = self.query_one(DataTable)
            table.clear(columns=False)

            filter_msg = ""
            if self.current_filter != FilterMode.NONE:
                filter_msg = f" (filter: {self.current_filter})"

            self.app.notify(
                f"No hosts match current filter{filter_msg}.",
                title="No Results",
                severity="error",
            )
            return

        table = self.query_one(DataTable)

        # Clear table but keep columns
        table.clear(columns=False)

        # Repopulate with filtered hosts
        self._populate_table(table, hosts)

        if task:
            logger.debug("Updated data table due to task: %s", task)
        else:
            logger.debug("Updated data table.")

        # Customize notification based on filter
        if self.current_filter == FilterMode.NONE:
            self.app.notify(
                "Table data refreshed successfully.", title="Refresh Complete"
            )
        else:
            self.app.notify(
                f"Showing {len(hosts)} host(s) with filter: {self.current_filter}",
                title="Refresh Complete",
            )

    def refresh_data_after_task(self, taskname: str) -> None:
        """Callback to refresh data views after task completion."""
        self.refresh_rows(taskname)

    def action_refresh_updates_all(self) -> None:
        """Action to refresh updates for all hosts."""

        self.run_task(
            taskname="refresh_updates",
            message="Refreshing updates for all hosts...",
            no_hosts_message="No hosts available to refresh updates.",
            save_state=True,
        )

    def action_sync_and_refresh_all(self) -> None:
        """Action to sync repositories and refresh updates for all hosts."""

        def sync_callback(_):
            """Callback to refresh updates after sync is complete"""
            self.action_refresh_updates_all()

        self.run_task(
            taskname="sync_repos",
            message="Syncing repositories for all hosts.\nThis may take a long time!",
            no_hosts_message="No hosts available to sync repositories.",
            save_state=False,  # Syncing repos does not affect state
            callback=sync_callback,
        )

    def action_filter_view(self) -> None:
        """Action to filter the inventory view."""

        if not getattr(context.inventory, "hosts", []):
            self.app.push_screen(ErrorScreen("No hosts available to filter."))
            return

        def handle_filter_selection(filter_mode: FilterMode | None) -> None:
            """Callback to handle filter selection"""
            if filter_mode is not None:
                self.current_filter = filter_mode
                self.refresh_rows("filter")
                self._update_status_bar()
                logger.info("Applied filter: %s", filter_mode)

        self.app.push_screen(FilterScreen(), handle_filter_selection)

    def _update_status_bar(self) -> None:
        """
        Update the inventory info status bar below.

        Normally will contain the stale data helper text, but will also
        display any applied filters to inform the user that they are
        viewing a partial table.

        Future status elements (if relevant) can also be updated here.
        """
        try:
            filter_label = self.query_one("#inventory-filter-label", Label)
        except Exception:
            logger.error("Filter label not found, this is unexpected and likely a bug.")
            return

        # Update filter label based on current filter
        match self.current_filter:
            case FilterMode.NONE:
                filter_label.update("")
            case FilterMode.UPDATES_ONLY:
                filter_label.update(f"Filtered: {FilterMode.UPDATES_ONLY}")
            case FilterMode.SECURITY_ONLY:
                filter_label.update(f"Filtered: {FilterMode.SECURITY_ONLY}")

    def get_filtered_hosts(self) -> list[Host]:
        """
        Get hosts from inventory matching the current filter.
        """
        inventory = context.inventory
        if not inventory:
            return []

        all_hosts = inventory.hosts

        match self.current_filter:
            case FilterMode.NONE:
                return all_hosts
            case FilterMode.UPDATES_ONLY:
                return [
                    host
                    for host in all_hosts
                    if host.supported and host.updates and len(host.updates) > 0
                ]
            case FilterMode.SECURITY_ONLY:
                return [
                    host
                    for host in all_hosts
                    if host.supported
                    and host.security_updates
                    and len(host.security_updates) > 0
                ]
            case _:
                logger.warning(
                    f"Unknown filter mode: {self.current_filter}, returning all hosts."
                )
                return all_hosts

    def _populate_table(self, table: DataTable, hosts: list[Host]) -> None:
        """Populate given table with host data"""

        def maybe_unknown(value: str | None, supported: bool = False) -> str:
            """Format as undiscovered if None or empty"""
            state = (
                "[dim](undiscovered)[/dim]" if supported else "[dim](unsupported)[/dim]"
            )
            return value if value else state

        for host in hosts:
            sec_count: int = len(host.security_updates) if host.security_updates else 0
            upd_count: int = len(host.updates) if host.updates else 0

            security_updates = (
                f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
            )
            updates = str(upd_count)

            # Do not show updates for unsupported hosts
            if not host.supported:
                security_updates = "[dim]—[/dim]"
                updates = "[dim]—[/dim]"

            if host.is_stale:
                updates += "[dim] *[/dim]"
                security_updates += "[dim] *[/dim]"

            status_str = (
                "[green]Online[/green]" if host.online else "[red]Offline[/red]"
            )

            table.add_row(
                host.name,
                maybe_unknown(host.os, host.supported),
                maybe_unknown(host.flavor, host.supported),
                maybe_unknown(host.version, host.supported),
                updates,
                security_updates,
                status_str,
            )
