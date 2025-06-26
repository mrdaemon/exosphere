import logging
from typing import cast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog

LOG_BUFFER = []
LOG_HANDLER = None


class UILogHandler(logging.Handler):
    """Custom logging handler to display logs in the UI"""

    def emit(self, record):
        msg = self.format(record)
        if hasattr(self, "log_widget") and self.log_widget:
            self.log_widget.write(msg)
            return

        # If log_widget is not set, store the message in a buffer
        LOG_BUFFER.append(msg)

    def set_log_widget(self, log_widget):
        """Set the log widget to write logs to."""
        self.log_widget = log_widget

        # Flush any buffered logs to the widget
        for msg in LOG_BUFFER:
            self.log_widget.write(msg)

        LOG_BUFFER.clear()


class LogsScreen(Screen):
    """Screen for the logs."""

    CSS_PATH = "style.tcss"

    def compose(self) -> ComposeResult:
        """Compose the logs layout."""

        # Create RichLog widget for displaying logs
        self.log_widget = RichLog(name="logs", auto_scroll=True, highlight=True)

        yield Header()
        yield self.log_widget
        yield Footer()

    def on_mount(self) -> None:
        """Set the title and subtitle of the logs."""
        self.title = "Exosphere"
        self.sub_title = "Logs Viewer"

        # Initialize the UILogHandler and set it to the app's log widget
        from exosphere.ui.app import ExosphereUi

        app = cast(ExosphereUi, self.app)
        app.ui_log_handler.set_log_widget(self.log_widget)

        logging.getLogger("exosphere.ui").debug(
            "Log view initialized, logs backfilled."
        )
