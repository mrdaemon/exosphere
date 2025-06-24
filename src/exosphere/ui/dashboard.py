from textual.app import ComposeResult
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label

from exosphere import context
from exosphere.objects import Host


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
