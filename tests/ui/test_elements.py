from unittest import mock

import pytest
from textual.app import App
from textual.widgets import ProgressBar

from exosphere.ui.elements import ErrorScreen, ProgressScreen, TaskRunnerScreen
from exosphere.ui.messages import HostStatusChanged


@pytest.fixture
def mock_app():
    app = mock.Mock(spec=App)
    app.pop_screen = mock.Mock()
    app.push_screen = mock.Mock()
    app.call_from_thread = mock.Mock()
    app.workers = mock.Mock()
    app.workers.cancel_node = mock.Mock()
    return app


@pytest.fixture
def mock_host():
    host = mock.Mock()
    host.name = "host1"
    return host


class TestErrorScreen:
    """Tests for ErrorScreen component."""

    def test_initialization(self):
        """Test that ErrorScreen initializes with correct message."""
        message = "Something went wrong"
        screen = ErrorScreen(message)
        assert screen.message == message


class TestProgressScreen:
    """Tests for ProgressScreen component."""

    @pytest.fixture
    def progress_screen(self, mock_host):
        return ProgressScreen("Running...", [mock_host], "test_task")

    def test_initialization(self, mock_host):
        """Test basic ProgressScreen initialization."""
        progress_screen = ProgressScreen(
            "Testing...", [mock_host], "test_task", save=False
        )

        assert progress_screen.message == "Testing..."
        assert len(progress_screen.hosts) == 1
        assert progress_screen.taskname == "test_task"
        assert progress_screen.save is False

    def test_on_mount_triggers_do_run(self, mocker, progress_screen):
        """Ensure that the task is ran once the screen is mounted."""
        mock_do_run = mocker.patch.object(progress_screen, "do_run")
        progress_screen.on_mount()
        mock_do_run.assert_called_once()

    def test_update_progress(self, mocker, progress_screen):
        """Ensure that the progress bar is updated correctly."""
        progress_bar = mocker.Mock(spec=ProgressBar)
        progress_screen.query_one = mocker.Mock(return_value=progress_bar)
        progress_screen.update_progress(2)
        progress_screen.query_one.assert_called_with("#task-progress-bar", ProgressBar)
        progress_bar.advance.assert_called_with(2)


class TestTaskRunnerScreen:
    """Tests for TaskRunnerScreen base class."""

    class ConcreteTaskRunnerScreen(TaskRunnerScreen):
        """Concrete implementation for testing TaskRunnerScreen."""

        def get_screen_name(self) -> str:
            return "test_screen"

        def refresh_data_after_task(self, taskname: str) -> None:
            pass  # No-op for tests

    @pytest.fixture
    def task_runner_screen(self):
        return self.ConcreteTaskRunnerScreen()

    @pytest.fixture
    def mock_context(self, mocker):
        """Mock context with inventory."""
        mock_inv = mocker.MagicMock()
        mock_inv.hosts = []
        mock_ctx = mocker.MagicMock()
        mock_ctx.inventory = mock_inv
        mocker.patch("exosphere.ui.elements.context", mock_ctx)
        return mock_ctx

    def test_get_screen_name_must_be_implemented(self):
        """Test that get_screen_name must be implemented by subclasses."""

        class IncompleteScreen(TaskRunnerScreen):
            def refresh_data_after_task(self, taskname: str) -> None:
                pass

        screen = IncompleteScreen()
        with pytest.raises(NotImplementedError):
            screen.get_screen_name()

    def test_run_task_no_inventory(self, mocker, task_runner_screen):
        """Test run_task with no inventory."""
        mocker.patch("exosphere.ui.elements.context.inventory", None)

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        task_runner_screen.run_task("test", "Testing...", "No hosts message")

        mock_app.push_screen.assert_called_once()
        args = mock_app.push_screen.call_args[0][0]
        assert "ErrorScreen" in str(type(args))
        assert "not initialized" in str(args.message).lower()

    def test_run_task_no_hosts(self, mocker, mock_context, task_runner_screen):
        """Test run_task with empty host list."""
        mock_context.inventory.hosts = []

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        task_runner_screen.run_task("test", "Testing...", "No hosts available")

        mock_app.push_screen.assert_called_once()
        args = mock_app.push_screen.call_args[0][0]
        assert "ErrorScreen" in str(type(args))
        assert args.message == "No hosts available"

    def test_run_task_with_hosts(
        self, mocker, mock_context, mock_host, task_runner_screen
    ):
        """Test run_task with hosts available."""
        mock_context.inventory.hosts = [mock_host]

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        task_runner_screen.run_task("ping", "Pinging...", "No hosts message")

        mock_app.push_screen.assert_called_once()
        args = mock_app.push_screen.call_args[0]
        assert "ProgressScreen" in str(type(args[0]))
        assert args[0].message == "Pinging..."
        assert args[0].taskname == "ping"

    def test_run_task_default_callback(
        self, mocker, mock_context, mock_host, task_runner_screen
    ):
        """Test run_task default callback sends message and refreshes data."""
        mock_context.inventory.hosts = [mock_host]

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        mock_post_message = mocker.patch.object(task_runner_screen, "post_message")
        mock_refresh = mocker.patch.object(
            task_runner_screen, "refresh_data_after_task"
        )

        task_runner_screen.run_task("ping", "Pinging...", "No hosts message")

        # Get the callback from push_screen call
        args = mock_app.push_screen.call_args[0]
        callback = (
            args[1]
            if len(args) > 1
            else mock_app.push_screen.call_args[1].get("callback")
        )

        # Simulate task completion
        callback(None)

        # Verify message was posted
        mock_post_message.assert_called_once()
        message = mock_post_message.call_args[0][0]
        assert isinstance(message, HostStatusChanged)
        assert message.current_screen == "test_screen"

        # Verify refresh was called
        mock_refresh.assert_called_once_with("ping")

    def test_run_task_custom_callback(
        self, mocker, mock_context, mock_host, task_runner_screen
    ):
        """Test run_task with custom callback."""
        mock_context.inventory.hosts = [mock_host]

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        custom_callback = mocker.MagicMock()

        task_runner_screen.run_task(
            "ping", "Pinging...", "No hosts message", callback=custom_callback
        )

        # Verify custom callback was passed to push_screen
        args = mock_app.push_screen.call_args[0]
        callback = (
            args[1]
            if len(args) > 1
            else mock_app.push_screen.call_args[1].get("callback")
        )
        assert callback == custom_callback

    def test_run_task_save_state_flag(
        self, mocker, mock_context, mock_host, task_runner_screen
    ):
        """Test run_task passes save_state flag to ProgressScreen."""
        mock_context.inventory.hosts = [mock_host]

        mock_app = mocker.MagicMock()
        mocker.patch.object(
            type(task_runner_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        # Test with save_state=False
        task_runner_screen.run_task(
            "ping", "Pinging...", "No hosts message", save_state=False
        )

        args = mock_app.push_screen.call_args[0]
        progress_screen = args[0]
        assert progress_screen.save is False
