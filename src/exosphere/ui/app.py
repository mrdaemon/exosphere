from textual.app import App, ComposeResult
from textual.widgets import Footer, Header


class ExosphereUi(App):
    """The main application class for the Exosphere UI."""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield Footer()
