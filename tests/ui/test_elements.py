from unittest import mock

import pytest
from textual.app import App
from textual.widgets import ProgressBar

from exosphere.inventory import HostOperation
from exosphere.ui.elements import DataScreen, ErrorScreen, ProgressScreen


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
        return ProgressScreen("Running...", [mock_host], HostOperation.PING)

    def test_initialization(self, mock_host):
        """Test basic ProgressScreen initialization."""
        progress_screen = ProgressScreen("Testing...", [mock_host], HostOperation.PING)

        assert progress_screen.message == "Testing..."
        assert len(progress_screen.hosts) == 1
        assert progress_screen.operation is HostOperation.PING

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

    def test_report_result_defaults_true(self, mock_host):
        """report_result defaults to True and can be disabled."""
        assert (
            ProgressScreen("m", [mock_host], HostOperation.PING).report_result is True
        )
        assert (
            ProgressScreen(
                "m", [mock_host], HostOperation.PING, report_result=False
            ).report_result
            is False
        )


class TestDataScreen:
    """Tests for the DataScreen base class."""

    def test_get_screen_name_must_be_implemented(self):
        """Test that get_screen_name must be implemented by subclasses."""

        class IncompleteScreen(DataScreen):
            def refresh_data_after_task(self, taskname: str, notify: bool = True):
                pass

        with pytest.raises(NotImplementedError):
            IncompleteScreen().get_screen_name()

    def test_refresh_data_after_task_must_be_implemented(self):
        """Test that refresh_data_after_task must be implemented by subclasses."""

        class IncompleteScreen(DataScreen):
            def get_screen_name(self) -> str:
                return "incomplete"

        with pytest.raises(NotImplementedError):
            IncompleteScreen().refresh_data_after_task("ping")
