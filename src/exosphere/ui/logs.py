"""
Logs Screen module
"""

import logging
import threading
from typing import cast

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog

logger = logging.getLogger("exosphere.ui.logs")

LOG_BUFFER = []
LOG_BUFFER_LOCK = threading.RLock()
LOG_HANDLER = None


class RichLogFormatter(logging.Formatter):
    """Custom formatter that adds Rich markup with level-specific colors."""

    LEVEL_COLORS = {
        "DEBUG": "dim",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def format(self, record):
        # Get the color for this log level
        level_color = self.LEVEL_COLORS.get(record.levelname, "white")

        # Create our custom format with proper alignment and colors
        timestamp = self.formatTime(record, self.datefmt)
        logger_name = record.name
        level_name = record.levelname
        message = record.getMessage()

        # Strip "exosphere." prefix to save space
        if logger_name.startswith("exosphere."):
            logger_name = logger_name[10:]  # Remove "exosphere."

        # Truncate logger name if still too long, keeping the most relevant part
        if len(logger_name) > 15:
            # Keep the last 15 characters (usually the most specific part)
            logger_name = "..." + logger_name[-12:]

        # Format with Rich markup and proper alignment
        formatted = (
            f"{timestamp} "
            f"[{level_color}]{level_name:<8}[/{level_color}] "
            f"[cyan]{logger_name:<15}[/cyan] "
            f"{message}"
        )

        return formatted


class UILogHandler(logging.Handler):
    """
    Custom logging handler to display logs in the UI

    Involves a running buffer to store logs until the log widget is set,
    which generally happens when the Logs screen is mounted.

    The log handler will backfill the log widget with any buffered logs
    at that point, and any new logs will be written directly to the
    widget, in the log screen.

    The buffering should be reasonably thread-safe, but it is a very
    clumsy and naive attempt at reentrant locking, since the
    application is made of a mix of threads and async coroutines.
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
        self.log_widget = RichLog(
            name="logs", auto_scroll=True, markup=True, highlight=True
        )

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
            logger.error("UI Log handler is not initialized. Cannot set log widget!")
            return

        app.ui_log_handler.set_log_widget(self.log_widget)

        logger.debug("Log view initialized")

    def on_unmount(self) -> None:
        """Clean up the log widget when the screen is unmounted."""
        from exosphere.ui.app import ExosphereUi

        app = cast(ExosphereUi, self.app)

        if app.ui_log_handler is None:
            logger.debug("UI Log handler is not initialized, nothing to clean up")
            return

        app.ui_log_handler.set_log_widget(None)
