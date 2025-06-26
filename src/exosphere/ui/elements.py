import logging

from textual import work
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Button, Label, ProgressBar
from textual.worker import get_current_worker

from exosphere import context
from exosphere.inventory import Inventory
from exosphere.objects import Host

logger = logging.getLogger("exosphere.ui.elements")


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


class ProgressScreen(Screen):
    """
    Screen for displaying progress of operations

    Also handles running the host tasks in a separate thread and
    updating the progress bar accordingly.

    Mostly wraps inventory.run_task to provide a UI for it.
    """

    CSS_PATH = "style.tcss"

    def __init__(self, message: str, hosts: list[Host], taskname: str) -> None:
        super().__init__()
        self.message = message
        self.hosts = hosts
        self.taskname = taskname

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
        self.do_run()

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.app.workers.cancel_node(self)

    def update_progress(self, step: int) -> None:
        """Update the progress bar."""
        self.query_one("#task-progress-bar", ProgressBar).advance(step)

    @work(exclusive=True, thread=True)
    def do_run(self) -> None:
        """Run the task and update the progress bar."""
        inventory: Inventory | None = context.inventory

        worker = get_current_worker()

        if inventory is None:
            logger.error("Inventory is not initialized, cannot run tasks.")
            self.app.call_from_thread(
                self.app.push_screen, ErrorScreen("Inventory is not initialized.")
            )
            return

        for host, _, exc in inventory.run_task(self.taskname, self.hosts):
            if exc:
                logger.error(
                    f"Error running {self.taskname} on host {host.name}: {str(exc)}"
                )
            else:
                logger.debug(
                    f"Successfully dispatched task {self.taskname} for host: {host.name}"
                )

            self.app.call_from_thread(self.update_progress, 1)

            if worker.is_cancelled:
                logger.warning("Task was cancelled, stopping progress update.")
                break

        logger.info(f"Finished running {self.taskname} on all hosts.")

        try:
            inventory.save_state()
            logger.debug("Inventory state saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save inventory state: {str(e)}")
            self.app.call_from_thread(
                self.app.push_screen,
                ErrorScreen(f"Failed to save inventory state:\n{str(e)}"),
            )

        self.app.call_from_thread(self.app.pop_screen)
