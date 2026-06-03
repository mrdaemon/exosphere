"""
Inventory Screen Module
"""

import logging
import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Grid, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import (
    Checkbox,
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
)

from exosphere import context
from exosphere.inventory import FilterMode, HostOperation, SortField
from exosphere.objects import Host, Update
from exosphere.ui.context import screenflags
from exosphere.ui.elements import DataScreen, ErrorScreen
from exosphere.ui.palette import HostCommandProvider

logger = logging.getLogger("exosphere.ui.inventory")


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


class SortScreen(Screen):
    """
    Screen for choosing a sort field and direction for the inventory view

    Presents a list of sortable columns plus a "reverse" checkbox.

    Dismisses with one of:
      * ``None``                  -> aborted
      * ``(None, reverse)``       -> default sort, restore config order
      * ``(SortField, reverse)``  -> chosen sort
    """

    CSS_PATH = "style.tcss"

    def __init__(
        self, current_sort: SortField | None = None, reverse: bool = False
    ) -> None:
        super().__init__()
        self._current_sort = current_sort
        self._reverse = reverse

    def compose(self) -> ComposeResult:
        items = [ListItem(Label("Default (config order)"), id="sort-none")]
        items.extend(
            ListItem(Label(field.label), id=f"sort-{field.value}")
            for field in SortField
        )

        # Preselect the current sort field, if any. Index 0 is the
        # "Default (config order)" entry, so fields are offset by one.
        initial_index = 0
        if self._current_sort is not None:
            initial_index = list(SortField).index(self._current_sort) + 1

        yield Center(
            Container(
                Label("Sort Inventory View", id="sort-title"),
                ListView(*items, id="sort-list", initial_index=initial_index),
                Checkbox("Reverse order", value=self._reverse, id="sort-reverse"),
                Label(
                    "[dim]↑/↓ + Enter to apply, 'r' to toggle reverse, "
                    "ESC to cancel[/dim]",
                    id="sort-help",
                ),
                classes="filter-message",
            ),
            id="sort-center",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """
        Handle list item selection

        Map to a SortField (or None for default order), read the reverse
        checkbox, and dismiss the screen with the resulting pair.
        """
        item_id = event.item.id

        # If something went terribly wrong, abort early.
        if not item_id:
            logger.warning("Selected item has no ID, cannot process sort selection!")
            return

        reverse = self.query_one("#sort-reverse", Checkbox).value

        if item_id == "sort-none":
            self.dismiss((None, reverse))
            event.stop()
            return

        token = item_id.removeprefix("sort-")
        try:
            field = SortField(token)
        except ValueError:
            logger.warning("Unknown sort field token '%s', ignoring selection.", token)
            return

        self.dismiss((field, reverse))
        event.stop()

    def on_key(self, event: Key) -> None:
        """Handle window key events for exit."""
        match event.key:
            case "escape":
                self.dismiss(None)
            case "r":
                # Toggle reverse on 'r' key for convenience
                reverse_checkbox = self.query_one("#sort-reverse", Checkbox)
                reverse_checkbox.value = not reverse_checkbox.value


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


class InventoryScreen(DataScreen):
    """Screen for the inventory."""

    CSS_PATH = "style.tcss"

    # Register command palette provider for the inventory screen
    COMMANDS = {HostCommandProvider}

    BINDINGS = [
        Binding("i", "app.none", show=False),
        ("ctrl+r", "refresh_updates_all", "Refresh Updates"),
        ("ctrl+x", "sync_and_refresh_all", "Sync & Refresh"),
        ("ctrl+f", "filter_view", "Filter"),
        ("ctrl+s", "sort_view", "Sort"),
    ]

    def __init__(self) -> None:
        """Initialize the inventory screen."""
        super().__init__()
        self.current_filter: FilterMode = FilterMode.NONE
        self.current_sort: SortField | None = None
        self.sort_reverse: bool = False

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
        hosts = self._get_display_hosts()

        if not hosts:
            logger.warning("Inventory is empty.")
            return

        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Column headers are driven by the SortField enum so they stay in
        # sync with the available sort fields.
        table.add_columns(*(field.label for field in SortField))

        self._populate_table(table, hosts)
        self._update_status_bar()

    def get_screen_name(self) -> str:
        """Return screen identifier."""
        return "inventory"

    def get_selected_host(self) -> Host | None:
        """
        Get the currently selected host under the data table's cursor

        Returns None if no host is selected or if the inventory is not
        initialized.
        """
        if not context.inventory:
            return None

        try:
            table = self.query_one(DataTable)
        except Exception as e:
            logger.debug("Couldn't fetch data table from screen: %s", str(e))
            return None

        if table.row_count == 0:
            logger.debug("Data table is empty, no host to select.")
            return None

        try:
            row = table.get_row_at(table.cursor_row)
        except Exception as e:
            logger.debug("Couldn't get row at cursor position: %s", str(e))
            return None

        # First column is the (plain, unmarked) host name.
        return context.inventory.get_host(str(row[0]))

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

    def refresh_rows(self, task: str | None = None, notify: bool = True) -> None:
        """Repopulate all rows in the data table from the inventory."""

        if not context.inventory:
            logger.error("Inventory is not initialized, cannot update rows.")
            self.app.push_screen(
                ErrorScreen("Inventory is not initialized, failed to refresh table")
            )
            return

        # Get filtered (and sorted) hosts for display
        hosts = self._get_display_hosts()

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

        # Customize notification based on filter, unless suppressed
        if not notify:
            return

        if self.current_filter == FilterMode.NONE:
            self.app.notify(
                "Table data refreshed successfully.", title="Refresh Complete"
            )
        else:
            self.app.notify(
                f"Showing {len(hosts)} host(s) with filter: {self.current_filter}",
                title="Refresh Complete",
            )

    def refresh_data_after_task(self, taskname: str, notify: bool = True) -> None:
        """Callback to refresh data views after task completion."""
        self.refresh_rows(taskname, notify=notify)

    def action_refresh_updates_all(self) -> None:
        """Action to refresh updates for all hosts."""
        self.app.run_host_operation_all(HostOperation.REFRESH)

    def action_sync_and_refresh_all(self) -> None:
        """Action to sync repositories and refresh updates for all hosts."""
        self.app.run_sync_refresh_all()

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

    def action_sort_view(self) -> None:
        """Action to sort the inventory view."""

        if not getattr(context.inventory, "hosts", []):
            self.app.push_screen(ErrorScreen("No hosts available to sort."))
            return

        def handle_sort_selection(
            result: tuple[SortField | None, bool] | None,
        ) -> None:
            """Callback to handle sort selection"""
            if result is None:
                return  # Cancelled, no change

            field, reverse = result
            self.current_sort = field
            self.sort_reverse = reverse
            self.refresh_rows("sort")
            self._update_status_bar()
            field_name = field.value if field is not None else "default"
            logger.info("Applied sort: %s (reverse=%s)", field_name, reverse)

        self.app.push_screen(
            SortScreen(self.current_sort, self.sort_reverse), handle_sort_selection
        )

    def _update_status_bar(self) -> None:
        """
        Update the inventory info status bar below.

        Displays any applied filter and/or sort to inform the user that
        they are viewing a partial or reordered table.

        Future status elements (if relevant) can also be updated here.
        """
        try:
            status_label = self.query_one("#inventory-filter-label", Label)
        except Exception:
            logger.error("Status label not found, this is unexpected and likely a bug.")
            return

        parts: list[str] = []

        if self.current_filter != FilterMode.NONE:
            parts.append(f"Filtered: {self.current_filter}")

        if self.current_sort is not None:
            arrow = "↓" if self.sort_reverse else "↑"
            parts.append(f"Sorted: {self.current_sort.label} {arrow}")

        status_label.update("  ".join(parts))

    def get_filtered_hosts(self) -> list[Host]:
        """
        Get hosts from inventory matching the current filter.
        """
        inventory = context.inventory
        if not inventory:
            return []

        return inventory.filter_hosts(self.current_filter)

    def _get_display_hosts(self) -> list[Host]:
        """
        Get hosts for display: filtered by the current filter, then sorted
        by the current sort field if one is active.
        """
        hosts = self.get_filtered_hosts()

        if self.current_sort is not None and context.inventory:
            hosts = context.inventory.sort_hosts(
                self.current_sort, hosts=hosts, reverse=self.sort_reverse
            )

        return hosts

    def _populate_table(self, table: DataTable, hosts: list[Host]) -> None:
        """Populate given table with host data"""

        def maybe_unknown(value: str | None, supported: bool = False) -> str:
            """Format as undiscovered if None or empty"""
            state = (
                "[dim](undiscovered)[/dim]" if supported else "[dim](unsupported)[/dim]"
            )
            return value if value else state

        for host in hosts:
            # Only populate update counts for supported and discovered
            # hosts, as other states do not carry meaningful data.
            if host.supported and host.os is not None:
                sec_count: int = (
                    len(host.security_updates) if host.security_updates else 0
                )
                upd_count: int = len(host.updates) if host.updates else 0

                security_updates = (
                    f"[red]{sec_count}[/red]" if sec_count > 0 else str(sec_count)
                )
                updates = str(upd_count)

                if host.is_stale:
                    updates += "[dim] *[/dim]"
                    security_updates += "[dim] *[/dim]"
            else:
                updates = "[dim]—[/dim]"
                security_updates = "[dim]—[/dim]"

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
