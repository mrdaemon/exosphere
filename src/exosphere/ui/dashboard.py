"""
Dashboard Screen module
"""

import logging

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label

from exosphere import context
from exosphere.objects import Host
from exosphere.ui.context import screenflags
from exosphere.ui.elements import ErrorScreen, ProgressScreen
from exosphere.ui.messages import HostStatusChanged

logger = logging.getLogger("exosphere.ui.dashboard")

# Arbitrary grid and widget sizing values
# They are arbitrary based on aesthetics.
MIN_WIDGET_WIDTH = 25  # Min host widget width, including borders and padding
MIN_GRID_COLUMNS = 2  # Minimum number of grid columns
MAX_GRID_COLUMNS = 8  # Maximum number of grid columns


class HostWidget(Widget):
    """Widget to display a host in the HostGrid."""

    def __init__(self, host: Host, id: str | None = None) -> None:
        self.host = host
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        """Compose the host widget layout."""
        box_style = "online" if self.host.online else "offline"

        # Container with vertical layout and host-box styling
        with Container(classes=f"host-box {box_style}"):
            # Host name
            yield Label(f"[b]{self.host.name}[/b]", classes="host-name")

            # Version info
            if not self.host.flavor or not self.host.version:
                version_text = "[dim](Undiscovered)[/dim]"
            else:
                version_text = f"[dim]{self.host.flavor} {self.host.version}[/dim]"
            yield Label(version_text, classes="host-version")

            # Description - The label is always emitted for consistent spacing
            description_value = getattr(self.host, "description", None)
            description_text = description_value or ""
            yield Label(description_text, classes="host-description")

            # Online Status
            status_text = (
                "[green]Online[/green]" if self.host.online else "[red]Offline[/red]"
            )
            yield Label(status_text, classes="host-status")

    def refresh_state(self) -> None:
        """Refresh the state of the host widget."""
        # Update the container's box style class
        container = self.query_one(Container)

        if self.host.online:
            container.add_class("online")
            container.remove_class("offline")
        else:
            container.add_class("offline")
            container.remove_class("online")

        # Update status label
        status_label = self.query_one(".host-status", Label)
        status_text = (
            "[green]Online[/green]" if self.host.online else "[red]Offline[/red]"
        )
        status_label.update(status_text)

        # Update version info, in case host is now discovered
        version_label = self.query_one(".host-version", Label)
        if not self.host.flavor or not self.host.version:
            version_text = "[dim](Undiscovered)[/dim]"
        else:
            version_text = f"[dim]{self.host.flavor} {self.host.version}[/dim]"
        version_label.update(version_text)


class DashboardScreen(Screen):
    """Screen for the dashboard."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("P", "ping_all_hosts", "Ping All"),
        ("ctrl+d", "discover_hosts", "Discover All"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()

        inventory = context.inventory
        hosts = getattr(inventory, "hosts", []) or []

        # "No hosts available" box
        if not hosts:
            with VerticalScroll(id="hosts-scroll"):
                with Container(id="empty-container"):
                    yield Label("No hosts available.", classes="empty-message")
            yield Footer()
            return

        # Grid container for host widgets
        with VerticalScroll(id="hosts-scroll"):
            with Container(id="hosts-container"):
                for host in hosts:
                    yield HostWidget(host)

        yield Footer()

    def on_resize(self, event) -> None:
        """Handle screen resize to update grid columns."""
        self.update_grid_columns()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"
        self.update_grid_columns()

    def update_grid_columns(self) -> None:
        """
        Update the grid column count based on screen width.

        This is as close as I can get (at least with my understanding
        of Textual) to reactive grids. We simply recalculate how many
        columns we can safely fit in based on entirely arbitrary values
        that "seem alright" for minimum tile width, and just update the
        CSS dynamically on resize.
        """

        terminal_width = self.size.width
        min_tile_width = MIN_WIDGET_WIDTH
        max_columns = max(1, terminal_width // min_tile_width)

        # Cap grid columns between minimum and maximum
        columns = min(max(MIN_GRID_COLUMNS, max_columns), MAX_GRID_COLUMNS)

        # Update the CSS dynamically - but only if the container exists
        # Early calls or empty dashboards may not have the container yet
        try:
            container = self.query_one("#hosts-container")
            if container:
                container.styles.grid_size_columns = columns
        except Exception:
            logger.debug(
                "Failed to update grid columns, container not found."
                " This is expected if the dashboard is empty or not mounted yet."
            )

    def refresh_hosts(self, task: str | None = None) -> None:
        """Refresh the host widgets."""
        if task:
            logger.debug(f"Refreshing host widgets after task: {task}")
        else:
            logger.debug("Refreshing host widgets")

        for host_widget in self.query(HostWidget):
            host_widget.refresh_state()

        self.app.notify("Host data successfully refreshed", title="Refresh Complete")

    def action_ping_all_hosts(self) -> None:
        """Action to ping all hosts."""

        self._run_task(
            taskname="ping",
            message="Pinging all hosts...",
            no_hosts_message="No hosts available to ping.",
        )

    def action_discover_hosts(self) -> None:
        """Action to discover all hosts."""

        self._run_task(
            taskname="discover",
            message="Discovering all hosts...",
            no_hosts_message="No hosts available to discover.",
        )

    def on_screen_resume(self) -> None:
        """Handle resume event to refresh host widgets."""
        if screenflags.is_screen_dirty("dashboard"):
            logger.debug("Dashboard screen is dirty, refreshing host widgets.")
            self.refresh_hosts()
            screenflags.flag_screen_clean("dashboard")

    def _run_task(self, taskname: str, message: str, no_hosts_message: str) -> None:
        """Run a task on all hosts."""

        def send_message(_):
            """
            Send a message indicating host status may have changed.
            """
            logger.debug(
                "Task '%s' completed, sending status change message.", taskname
            )
            self.post_message(HostStatusChanged("dashboard"))
            self.refresh_hosts(taskname)

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
                save=True,  # All dashboard operations affect state
            ),
            callback=send_message,  # Signal everyone that hosts changed
        )
