"""
Common UI Elements Module

This module defines common UI elements used across the Exosphere TUI
application, such as error screens and progress screens.

These elements are responsible for displaying errors, initiating tasks
while presenting progress or asking input from the user.

The Task Dispatch logic for UI Screens is implemented here.
"""

import logging
from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar
from textual.worker import get_current_worker

from exosphere import app_config, context
from exosphere.inventory import HostOperation, Inventory
from exosphere.objects import Host

if TYPE_CHECKING:
    from exosphere.ui.app import ExosphereUi

logger = logging.getLogger("exosphere.ui.elements")


class DataScreen(Screen):
    """
    Base class for screens that display host data and must redraw after
    a host operation has potentially changed it.

    Dispatch lives on the app (:meth:`ExosphereUi.run_host_task`); this
    base only defines the *refresh protocol* the app drives after a task:

    - get_screen_name() -> str (the screen's identifier in the
      ``screenflags`` registry)
    - refresh_data_after_task(taskname, notify) -> None (redraw this
      screen's data widgets)

    After a task, the app refreshes the currently-visible data screen via
    refresh_data_after_task() and flags the others dirty so they redraw on
    resume.

    Exosphere has a lot of widgets that are difficult to make reactive,
    such as data tables and grid views, especially across modal screens
    that can be inactive at any point, so this screen-level refresh
    protocol is the most straightforward workaround.

    Screens dispatch with ``self.app.run_host_task(...)``; the ``app``
    type below is narrowed so that call resolves without a cast.
    """

    if TYPE_CHECKING:
        # Type hint the app attribute to the module for exposed methods
        # like run_host_task, which screens will call directly.
        app: "ExosphereUi"

    def refresh_data_after_task(self, taskname: str, notify: bool = True) -> None:
        """
        Refresh screen data after task completion.

        Subclasses must implement this to define their refresh behavior.

        :param taskname: Name of the task that was completed, for context.
        :param notify: Whether to send a UI notification after refreshing.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement refresh_data_after_task()"
        )

    def get_screen_name(self) -> str:
        """Return the screen identifier for this screen."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_screen_name()"
        )


class ErrorScreen(Screen):
    """
    Error message dialog box screen

    Displays a specified message and an "Ok" button, which pops
    the screen when pressed. Useful for displaying interactive error
    messages to the user.
    """

    CSS_PATH = "style.tcss"

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Center(Label(self.message)),
            Center(Button("Ok", id="ok-button")),
            classes="error-message",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press to close the error screen."""
        if event.button.id == "ok-button":
            self.app.pop_screen()

        # Do not bubble the event up in the ui
        event.stop()


class ProgressScreen(Screen):
    """
    Screen for displaying progress of operations

    Also handles running the host tasks in a separate thread and
    updating the progress bar accordingly.

    The save parameter controls whether the inventory state will be
    serialized to disk after the task completes, if autosave is enabled
    in the application configuration. Defaults to True.

    Mostly wraps inventory.run_task to provide a UI for it.
    """

    CSS_PATH = "style.tcss"

    def __init__(
        self,
        message: str,
        hosts: list[Host],
        operation: HostOperation,
        save: bool = True,
    ) -> None:
        super().__init__()
        self.message = message
        self.hosts = hosts
        self.operation = operation
        self.save = save

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.message),
            ProgressBar(
                total=len(self.hosts),
                show_eta=False,
                show_percentage=True,
                show_bar=True,
                id="task-progress-bar",
            ),
            Label("Press ESC to abort", id="abort-message"),
            classes="progress-message",
        )

    def on_mount(self) -> None:
        """Run the task when the screen is ready."""
        self.do_run()

    def on_key(self, event: Key) -> None:
        """Handle key events, specifically ESC to abort the task."""
        if event.key == "escape":
            logger.warning("Aborting task on user request!")
            self.query_one("#abort-message", Label).update(
                "[$text-error]Aborting...[/]"
            )
            self.app.workers.cancel_node(self)

        # Do not bubble the event up in the UI
        event.stop()

    def update_progress(self, step: int) -> None:
        """Update the progress bar."""
        self.query_one("#task-progress-bar", ProgressBar).advance(step)

    @work(exclusive=True, thread=True)
    def do_run(self) -> None:
        """
        Run the task and update the progress bar.

        Runs in a separate, exclusive thread to avoid blocking the UI
        while the ThreadPoolExecutor runs the task on all hosts.
        """
        inventory: Inventory | None = context.inventory

        worker = get_current_worker()

        if inventory is None:
            logger.error("Inventory is not initialized, cannot run tasks.")
            self.app.call_from_thread(
                self.app.push_screen, ErrorScreen("Inventory is not initialized.")
            )
            return

        # Keep track of exception count, for later UI notify
        exc_count: int = 0
        was_cancelled: bool = False

        # Dispatch task through worker pool inventory API
        for host, _, exc in inventory.run_task(self.operation, self.hosts):
            if exc:
                exc_count += 1
                logger.error(
                    f"Error running {self.operation.value} on host {host.name}: {str(exc)}"
                )
            else:
                logger.debug(
                    f"Successfully dispatched task {self.operation.value} for host: {host.name}"
                )

            self.app.call_from_thread(self.update_progress, 1)

            if worker.is_cancelled:
                was_cancelled = True
                logger.warning("Task was cancelled, stopping progress update.")
                break

        logger.info("Finished running %s on all hosts.", self.operation.value)

        # Attempt to serialize state to database if autosave is enabled
        # Unless whatever pushed the screen requested otherwise.
        if self.save and app_config["options"]["cache_autosave"]:
            try:
                inventory.save_state()
                logger.debug("Inventory state saved successfully.")
            except Exception as e:
                logger.error("Failed to save inventory state: %s", str(e))
                self.app.call_from_thread(
                    self.app.push_screen,
                    ErrorScreen(f"Failed to save inventory state:\n{str(e)}"),
                )

        # Send notification if task was cancelled
        if was_cancelled:
            self.app.call_from_thread(
                self.app.notify,
                "Task cancelled by user.",
                title="Cancelled",
                severity="error",
            )

        # Send a notification if task completed with errors
        if exc_count > 0:
            self.app.call_from_thread(
                self.app.notify,
                f"Task completed with {exc_count} error(s).\nSee logs panel for details.",
                title="Task Errors",
                severity="error",
            )

        # Pop the screen and return the task name as argument to the
        # (optional) callback set when the screen was pushed.
        self.app.call_from_thread(self.dismiss, self.operation.value)
