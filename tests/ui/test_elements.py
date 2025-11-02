from unittest import mock

import pytest
from textual.app import App
from textual.widgets import ProgressBar

from exosphere.ui.elements import ErrorScreen, ProgressScreen


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
def error_screen():
    return ErrorScreen("Test error message")


@pytest.fixture
def mock_host():
    host = mock.Mock()
    host.name = "host1"
    return host


@pytest.fixture
def progress_screen(mock_host):
    return ProgressScreen("Running...", [mock_host], "test_task")


def test_error_screen_initialization():
    """Test that ErrorScreen initializes with correct message."""
    message = "Something went wrong"
    screen = ErrorScreen(message)
    assert screen.message == message


def test_progress_screen_initialization(mock_host):
    """Test basic ProgressScreen initialization."""
    progress_screen = ProgressScreen("Testing...", [mock_host], "test_task", save=False)

    assert progress_screen.message == "Testing..."
    assert len(progress_screen.hosts) == 1
    assert progress_screen.taskname == "test_task"
    assert progress_screen.save is False


def test_progress_screen_on_mount_triggers_do_run(mocker, progress_screen):
    """Ensure that the task is ran once the screen is mounted."""
    mock_do_run = mocker.patch.object(progress_screen, "do_run")
    progress_screen.on_mount()
    mock_do_run.assert_called_once()


def test_progress_screen_update_progress(mocker, progress_screen):
    """Ensure that the progress bar is updated correctly."""
    progress_bar = mocker.Mock(spec=ProgressBar)
    progress_screen.query_one = mocker.Mock(return_value=progress_bar)
    progress_screen.update_progress(2)
    progress_screen.query_one.assert_called_with("#task-progress-bar", ProgressBar)
    progress_bar.advance.assert_called_with(2)
