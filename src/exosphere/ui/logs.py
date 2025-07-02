import logging
import threading
from typing import cast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog

LOG_BUFFER = []
LOG_BUFFER_LOCK = threading.RLock()
LOG_HANDLER = None


class UILogHandler(logging.Handler):
    """
    Custom logging handler to display logs in the UI

    Involves a running buffer to store logs until the log widget is set,
    which generally happens when the Logs screen is mounted.

    The log handler will backfill the log widget with any buffered logs
    at that point, and any new logs will be written directly to the
    widget, in the log screen.

    The buffering should be reasonably thread-safe, but it is a very
    clumsy and naive attempt at reentrant locking.
    """

    def emit(self, record) -> None:
        msg = self.format(record)
        if hasattr(self, "log_widget") and self.log_widget:
            self.log_widget.write(msg)
            return

        # If log_widget is not set, store the message in a buffer
        with LOG_BUFFER_LOCK:
            LOG_BUFFER.append(msg)

    def set_log_widget(self, log_widget: RichLog | None) -> None:
        """Set the log widget to write logs to."""
        self.log_widget = log_widget

        # Widget has been cleared, no need to do anything else
        if not self.log_widget:
            return

        logging.getLogger("exosphere.ui").debug(
            "Flushing buffered logs to the log widget."
        )

        # Flush any buffered logs to the widget
        with LOG_BUFFER_LOCK:
            for msg in LOG_BUFFER:
                try:
                    self.log_widget.write(msg)
                except Exception as e:
                    logging.getLogger("exosphere.ui").error(
                        f"Error writing buffered log message to log pane!: {str(e)}"
                    )

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

        if app.ui_log_handler is None:
            logging.getLogger("exosphere.ui").error(
                "UI Log handler is not initialized. Cannot set log widget!"
            )
            return

        app.ui_log_handler.set_log_widget(self.log_widget)

        logging.getLogger("exosphere.ui").debug("Log view initialized")

    def on_unmount(self) -> None:
        """Clean up the log widget when the screen is unmounted."""
        from exosphere.ui.app import ExosphereUi

        app = cast(ExosphereUi, self.app)

        if app.ui_log_handler is None:
            logging.getLogger("exosphere.ui").debug(
                "UI Log handler is not initialized, nothing to clean up"
            )
            return

        app.ui_log_handler.set_log_widget(None)
