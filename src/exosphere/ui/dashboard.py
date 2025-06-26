import logging

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label, ProgressBar
from textual.worker import get_current_worker

from exosphere import context
from exosphere.inventory import Inventory
from exosphere.objects import Host

logger = logging.getLogger("exosphere.ui.dashboard")


class HostWidget(Widget):
    """Widget to display a host in the HostGrid."""

    def __init__(self, host: Host) -> None:
        self.host = host
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the host widget layout."""
        box_style = "online" if self.host.online else "offline"
        status = "[green]Online[/green]" if self.host.online else "[red]Offline[/red]"
        description = f"{self.host.description}\n\n" if self.host.description else "\n"

        yield Label(
            f"[b]{self.host.name}[/b]\n"
            f"[dim]{self.host.flavor} {self.host.version}[/dim]\n"
            f"{description}"
            f"{status}",
            classes=f"host-box {box_style}",
            shrink=True,
            expand=True,
        )


class ProgressScreen(Screen):
    """Screen for displaying progress of operations"""

    CSS_PATH = "style.tcss"

    def __init__(self, message: str, hosts: list[Host], taskname: str) -> None:
        super().__init__()
        self.message = message
        self.hosts = hosts
        self.taskname = taskname

    def compose(self) -> ComposeResult:
        yield Vertical(
            ProgressBar(
                total=len(self.hosts),
                show_eta=False,
                show_percentage=True,
                show_bar=True,
            ),
            Label(self.message),
            classes="progress-message",
        )

    def on_mount(self) -> None:
        self.do_run()

    def update_progress(self, step: int) -> None:
        """Update the progress bar."""
        self.query_one(ProgressBar).advance(step)

    @work(exclusive=True, thread=True)
    def do_run(self) -> None:
        """Run the task and update the progress bar."""
        inventory: Inventory | None = context.inventory

        worker = get_current_worker()

        if inventory is None:
            logger.error("Inventory is not initialized, cannot run tasks.")
            self.app.pop_screen()
            return

        for host, _, exc in inventory.run_task(self.taskname, self.hosts):
            if exc:
                logger.error(
                    f"Error running {self.taskname} on host {host.name}: {str(exc)}"
                )
            else:
                logger.info(
                    f"Successfully ran task {self.taskname} on host: {host.name}"
                )

            self.app.call_from_thread(self.update_progress, 1)

            if worker.is_cancelled:
                logger.info("Task was cancelled, stopping progress update.")
                break

        logger.info(f"Finished running {self.taskname} on all hosts.")
        self.app.call_from_thread(self.app.pop_screen)


class DashboardScreen(Screen):
    """Screen for the dashboard."""

    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("P", "ping_all_hosts", "Ping All"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()

        inventory = context.inventory

        hosts = inventory.hosts if inventory else []

        if not hosts:
            yield Label("No hosts available.", classes="empty-message")
            yield Footer()
            return

        for host in hosts:
            yield HostWidget(host)

        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the dashboard."""
        self.title = "Exosphere"
        self.sub_title = "Dashboard"

    def action_ping_all_hosts(self) -> None:
        """Action to ping all hosts."""

        inventory = context.inventory
        hosts = inventory.hosts if inventory else []

        if not hosts:
            self.app.console.print(
                "[red]No hosts available to ping.[/red]",
                style="bold",
            )
            return

        self.app.push_screen(
            ProgressScreen(
                message="Pinging all hosts...",
                hosts=hosts,
                taskname="ping",
            )
        )
