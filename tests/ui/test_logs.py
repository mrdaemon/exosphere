import logging
import threading

import pytest
from textual.widgets import RichLog

from exosphere.ui.logs import LogsScreen, UILogHandler


@pytest.fixture
def ui_log_handler():
    """Create a fresh UILogHandler for testing."""
    handler = UILogHandler()
    yield handler
    handler.close()


@pytest.fixture
def mock_rich_log(mocker):
    """Create a mock RichLog widget."""
    return mocker.create_autospec(RichLog, instance=True)


@pytest.fixture
def mock_app(mocker):
    """Create a mock app with ui_log_handler."""
    app = mocker.MagicMock()
    app.ui_log_handler = mocker.create_autospec(UILogHandler, instance=True)
    return app


@pytest.fixture(autouse=True)
def clear_log_buffer():
    """Clear the log buffer before each test to avoid test interference."""
    UILogHandler.clear_buffer()


class TestUILogHandler:
    """Tests for the UILogHandler class."""

    def test_init(self, ui_log_handler):
        """Test UILogHandler initialization."""
        assert not hasattr(ui_log_handler, "log_widget")

    def test_emit_without_log_widget_buffers_message(self, ui_log_handler):
        """Test that messages are buffered when no log widget is set."""
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Emit the record
        ui_log_handler.emit(record)

        # Check that the message is in the buffer
        buffer_contents = UILogHandler.get_buffer_contents()
        assert len(buffer_contents) == 1
        assert "Test message" in buffer_contents[0]

    def test_emit_with_log_widget_writes_directly(self, ui_log_handler, mock_rich_log):
        """Test that messages are written directly when log widget is set."""
        # Set the log widget
        ui_log_handler.set_log_widget(mock_rich_log)

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Emit the record
        ui_log_handler.emit(record)

        # Check that write was called on the log widget
        mock_rich_log.write.assert_called_once()
        args = mock_rich_log.write.call_args[0]
        assert "Test message" in args[0]

        # Check that buffer is empty
        assert UILogHandler.get_buffer_size() == 0

    def test_set_log_widget_none_clears_widget(self, ui_log_handler, mock_rich_log):
        """Test that setting log widget to None clears it."""
        # First set a widget
        ui_log_handler.set_log_widget(mock_rich_log)
        assert ui_log_handler.log_widget == mock_rich_log

        # Clear the widget
        ui_log_handler.set_log_widget(None)
        assert ui_log_handler.log_widget is None

    def test_set_log_widget_flushes_buffer(self, ui_log_handler, mock_rich_log, mocker):
        """Test that setting a log widget flushes the buffer."""
        # Add some messages to the buffer first by emitting logs
        for i in range(1, 4):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=i,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            ui_log_handler.emit(record)

        # Mock the logger to avoid actual log output during test
        mock_logger = mocker.patch("exosphere.ui.logs.logging.getLogger")

        # Set the log widget
        ui_log_handler.set_log_widget(mock_rich_log)

        # Check that all buffered messages were written
        assert mock_rich_log.write.call_count == 3
        calls = mock_rich_log.write.call_args_list
        assert calls[0][0][0] == "Message 1"
        assert calls[1][0][0] == "Message 2"
        assert calls[2][0][0] == "Message 3"

        # Check that buffer is now empty
        assert UILogHandler.get_buffer_size() == 0

        # Check that debug message was logged
        mock_logger.assert_called_with("exosphere.ui")
        mock_logger.return_value.debug.assert_called_with(
            "Flushing buffered logs to the log widget."
        )

    def test_set_log_widget_handles_write_exception(
        self, ui_log_handler, mock_rich_log, mocker
    ):
        """Test that exceptions during buffer flush are handled gracefully."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        ui_log_handler.emit(record)

        # Make the log widget throw an exception
        mock_rich_log.write.side_effect = Exception("Write failed")

        # Mock the logger
        mock_logger = mocker.patch("exosphere.ui.logs.logging.getLogger")

        # Set the log widget - should not raise an exception
        ui_log_handler.set_log_widget(mock_rich_log)

        # Check that error was logged
        mock_logger.return_value.error.assert_called_with(
            "Error writing buffered log message to log pane!: Write failed"
        )

        # Buffer should still be cleared even though write failed
        assert UILogHandler.get_buffer_size() == 0

    def test_threading_safety(self, ui_log_handler):
        """Test that the handler works safely across multiple threads."""
        results = []

        def emit_log(message):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=message,
                args=(),
                exc_info=None,
            )
            ui_log_handler.emit(record)
            results.append(message)

        # Create multiple threads that emit logs
        threads = []
        for i in range(10):
            thread = threading.Thread(target=emit_log, args=(f"Message {i}",))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that all messages made it to the buffer
        buffer_contents = UILogHandler.get_buffer_contents()
        assert len(buffer_contents) == 10
        # All messages should be present (order may vary due to threading)
        buffer_messages = set(buffer_contents)
        expected_messages = {f"Message {i}" for i in range(10)}
        assert any(
            expected in msg for expected in expected_messages for msg in buffer_messages
        )


class TestLogsScreen:
    """Tests for the LogsScreen class."""

    def test_compose(self, mocker):
        """Test that LogsScreen compose method creates the correct widgets."""
        screen = LogsScreen()

        # Mock the compose dependencies
        mock_header = mocker.patch("exosphere.ui.logs.Header")
        mock_footer = mocker.patch("exosphere.ui.logs.Footer")
        mock_richlog = mocker.patch("exosphere.ui.logs.RichLog")

        # Call compose and convert to list to trigger the generator
        list(screen.compose())

        # Check that all widgets were created
        mock_header.assert_called_once()
        mock_richlog.assert_called_once_with(
            name="logs", auto_scroll=True, markup=True, highlight=True
        )
        mock_footer.assert_called_once()

        # Check that the log_widget attribute was set
        assert hasattr(screen, "log_widget")

    def test_on_mount_with_valid_handler(self, mocker, mock_app):
        """Test on_mount when ui_log_handler is available."""
        screen = LogsScreen()
        screen.log_widget = mocker.create_autospec(RichLog, instance=True)

        # Mock the app property
        mocker.patch.object(
            type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
        )

        # Mock the logger
        mock_logger = mocker.patch("exosphere.ui.logs.logger")

        # Call on_mount
        screen.on_mount()

        # Check that title and subtitle were set
        assert screen.title == "Exosphere"
        assert screen.sub_title == "Logs Viewer"

        # Check that set_log_widget was called
        mock_app.ui_log_handler.set_log_widget.assert_called_once_with(
            screen.log_widget
        )

        # Check that debug message was logged
        mock_logger.debug.assert_called_with("Log view initialized")

    def test_on_mount_with_no_handler(self, mocker, mock_app):
        """Test on_mount when ui_log_handler is None."""
        screen = LogsScreen()
        screen.log_widget = mocker.create_autospec(RichLog, instance=True)

        # Set ui_log_handler to None
        mock_app.ui_log_handler = None

        # Mock the app property
        mocker.patch.object(
            type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
        )

        # Mock the logger
        mock_logger = mocker.patch("exosphere.ui.logs.logger")

        # Call on_mount
        screen.on_mount()

        # Check that error was logged
        mock_logger.error.assert_called_with(
            "UI Log handler is not initialized. Cannot set log widget!"
        )

    def test_on_unmount_with_valid_handler(self, mocker, mock_app):
        """Test on_unmount when ui_log_handler is available."""
        screen = LogsScreen()

        # Mock the app property
        mocker.patch.object(
            type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
        )

        # Call on_unmount
        screen.on_unmount()

        # Check that set_log_widget was called with None
        mock_app.ui_log_handler.set_log_widget.assert_called_once_with(None)

    def test_on_unmount_with_no_handler(self, mocker, mock_app):
        """Test on_unmount when ui_log_handler is None."""
        screen = LogsScreen()

        # Set ui_log_handler to None
        mock_app.ui_log_handler = None

        # Mock the app property
        mocker.patch.object(
            type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
        )

        # Mock the logger
        mock_logger = mocker.patch("exosphere.ui.logs.logger")

        # Call on_unmount
        screen.on_unmount()

        # Check that debug message was logged
        mock_logger.debug.assert_called_with(
            "UI Log handler is not initialized, nothing to clean up"
        )

    def test_css_path_defined(self):
        """Test that CSS_PATH is defined correctly."""
        screen = LogsScreen()
        assert screen.CSS_PATH == "style.tcss"


class TestLogBufferGlobals:
    """Tests for the class-level buffer for thread safety."""

    def test_log_buffer_initial_state(self):
        """Test that UILogHandler buffer starts empty (cleared by fixture)."""
        buffer_contents = UILogHandler.get_buffer_contents()
        assert isinstance(buffer_contents, list)
        assert len(buffer_contents) == 0


class TestIntegration:
    """Integration tests for the logging system."""

    def test_full_logging_workflow(self, ui_log_handler, mock_rich_log, mocker):
        """Test the complete workflow from buffering to widget display."""
        # Mock the logger to avoid actual output
        mocker.patch("exosphere.ui.logs.logging.getLogger")

        # Step 1: Emit logs without widget (should buffer)
        record1 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Buffered message 1",
            args=(),
            exc_info=None,
        )
        record2 = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=2,
            msg="Buffered message 2",
            args=(),
            exc_info=None,
        )

        ui_log_handler.emit(record1)
        ui_log_handler.emit(record2)

        # Check buffer has messages
        assert UILogHandler.get_buffer_size() == 2

        # Step 2: Set widget (should flush buffer)
        ui_log_handler.set_log_widget(mock_rich_log)

        # Check buffer was flushed to widget
        assert mock_rich_log.write.call_count == 2
        assert UILogHandler.get_buffer_size() == 0

        # Step 3: Emit new log (should go directly to widget)
        record3 = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=3,
            msg="Direct message",
            args=(),
            exc_info=None,
        )
        ui_log_handler.emit(record3)

        # Check new message went directly to widget
        assert mock_rich_log.write.call_count == 3
        assert UILogHandler.get_buffer_size() == 0

        # Step 4: Clear widget (should reset to buffering mode)
        ui_log_handler.set_log_widget(None)

        record4 = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=4,
            msg="Buffered again",
            args=(),
            exc_info=None,
        )
        ui_log_handler.emit(record4)

        # Should be back to buffering
        buffer_contents = UILogHandler.get_buffer_contents()
        assert len(buffer_contents) == 1
        assert "Buffered again" in buffer_contents[0]
