from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Placeholder


class LogsScreen(Screen):
    """Screen for the logs."""

    def compose(self) -> ComposeResult:
        """Compose the logs layout."""
        yield Header()
        yield Placeholder(name="logs_content", label="Logs Content")
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the logs."""
        self.title = "Exosphere"
        self.sub_title = "Logs Viewer"
