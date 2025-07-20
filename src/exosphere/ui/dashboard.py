import logging

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label

from exosphere import context
from exosphere.objects import Host
from exosphere.ui.context import screenflags
from exosphere.ui.elements import ErrorScreen, ProgressScreen
from exosphere.ui.messages import HostStatusChanged

logger = logging.getLogger("exosphere.ui.dashboard")


class HostWidget(Widget):
    """Widget to display a host in the HostGrid."""

    def __init__(self, host: Host, id: str | None = None) -> None:
        self.host = host
        super().__init__(id=id)

    def make_contents(self) -> str:
        """Generate the contents of the host widget."""
        status = "[green]Online[/green]" if self.host.online else "[red]Offline[/red]"

        if not self.host.flavor or not self.host.version:
            version = "(Undiscovered)"
        else:
            version = f"{self.host.flavor} {self.host.version}"

        description_value = getattr(self.host, "description", None)
        description = f"{description_value}\n\n" if description_value else "\n"

        return f"[b]{self.host.name}[/b]\n[dim]{version}[/dim]\n{description}{status}"

    def compose(self) -> ComposeResult:
        """Compose the host widget layout."""
        box_style = "online" if self.host.online else "offline"

        yield Label(
            self.make_contents(),
            classes=f"host-box {box_style}",
            shrink=True,
            expand=True,
        )

    def refresh_state(self) -> None:
        """Refresh the state of the host widget."""
        contents = self.query_one(Label)
        contents.update(self.make_contents())

        # Change box style class based on online status
        if self.host.online:
            contents.add_class("online")
            contents.remove_class("offline")
        else:
            contents.add_class("offline")
            contents.remove_class("online")


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

        if not hosts:
            yield Label("No hosts available.", classes="empty-message")
            yield Footer()
            return

        for host in hosts:
            yield HostWidget(host, id=f"host-{host.name}")

        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"

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
            """Send a message indicating the task is complete."""
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
