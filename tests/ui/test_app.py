import asyncio
import logging

import pytest
from textual.widgets import Footer, Header

from exosphere.ui.app import ExosphereUi
from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, UILogHandler
from exosphere.ui.messages import HostStatusChanged


class TestExosphereUi:
    """
    Test suite for the ExosphereUi application class

    Tests essentially the entry point for the UI, including
    common setup, expected widgets and behaviors, and event handlers
    that need to be at the root of all the modal screens.
    """

    @pytest.fixture
    def mock_screenflags(self, mocker):
        """Mock the screenflags registry."""
        return mocker.patch("exosphere.ui.app.screenflags")

    @pytest.fixture
    def mock_ui_log_handler(self, mocker):
        """Mock UILogHandler class."""
        return mocker.patch("exosphere.ui.app.UILogHandler")

    @pytest.fixture
    def mock_logger(self, mocker):
        """Mock the exosphere logger."""
        return mocker.patch("logging.getLogger")

    @pytest.fixture
    def app(self):
        """Create an ExosphereUi instance for testing."""
        return ExosphereUi()

    def test_app_initialization(self, app):
        """Test that the ExosphereUi app initializes correctly."""
        # Verify we have the correct class
        assert isinstance(app, ExosphereUi)

        # ui_log_handler is not set until on_mount is called
        assert not hasattr(app, "ui_log_handler") or app.ui_log_handler is None

        # Basic verification that required attributes exist
        assert hasattr(app, "BINDINGS")
        assert hasattr(app, "MODES")
        assert len(app.BINDINGS) > 0
        assert len(app.MODES) > 0

    def test_modes_and_screen_classes(self, app):
        """Test that MODES are configured correctly with proper screen classes."""
        # Basic structure validation
        assert len(app.MODES) == 3
        assert isinstance(app.MODES, dict)

        # Verify specific mode mappings
        assert app.MODES["dashboard"] == DashboardScreen
        assert app.MODES["inventory"] == InventoryScreen
        assert app.MODES["logs"] == LogsScreen

        # Verify all values are proper classes
        for mode_name, screen_class in app.MODES.items():
            assert isinstance(mode_name, str)
            assert isinstance(screen_class, type)
            assert hasattr(screen_class, "__name__")

        # Verify class names match expectations
        assert app.MODES["dashboard"].__name__ == "DashboardScreen"
        assert app.MODES["inventory"].__name__ == "InventoryScreen"
        assert app.MODES["logs"].__name__ == "LogsScreen"

    def test_bindings_configuration(self, app):
        """
        Test that bindings are configured correctly.

        The core bindings are more or less expected to be present
        across all screens in the modal application, so we just check
        them here. This could be removed if they change a lot, but
        it's low cost to do that check for now.
        """
        # Check binding structure - each binding is a tuple (key, action, description)
        assert len(app.BINDINGS) == 4

        # Extract keys and actions from bindings (tuples)
        keys = [binding[0] for binding in app.BINDINGS]
        actions = [binding[1] for binding in app.BINDINGS]
        descriptions = [binding[2] for binding in app.BINDINGS]

        assert "d" in keys
        assert "i" in keys
        assert "l" in keys
        assert "^q" in keys

        assert "switch_mode('dashboard')" in actions
        assert "switch_mode('inventory')" in actions
        assert "switch_mode('logs')" in actions
        assert "quit" in actions

        assert "Dashboard" in descriptions
        assert "Inventory" in descriptions
        assert "Logs" in descriptions
        assert "Quit" in descriptions

    def test_compose_yields_header_and_footer(self, app):
        """Test that compose method yields exactly Header and Footer widgets."""
        compose_result = list(app.compose())

        assert len(compose_result) == 2
        assert isinstance(compose_result[0], Header)
        assert isinstance(compose_result[1], Footer)

    def test_on_mount_initializes_properly(
        self, app, mock_screenflags, mock_ui_log_handler, mock_logger, mocker
    ):
        """Test that on_mount initializes the app state correctly."""
        # Mock switch_mode method
        mock_switch_mode = mocker.patch.object(app, "switch_mode")

        # Mock the logging formatter
        mock_formatter = mocker.Mock()
        mocker.patch("logging.Formatter", return_value=mock_formatter)

        # Create a mock handler instance
        mock_handler_instance = mocker.Mock(spec=UILogHandler)
        mock_ui_log_handler.return_value = mock_handler_instance

        # Mock the exosphere logger
        mock_exosphere_logger = mocker.Mock()
        mock_logger.return_value = mock_exosphere_logger

        # Call on_mount
        app.on_mount()

        # Verify screenflags.register_screens was called
        mock_screenflags.register_screens.assert_called_once_with(
            "dashboard", "inventory"
        )

        # Verify UILogHandler was created and configured
        mock_ui_log_handler.assert_called_once()
        mock_handler_instance.setFormatter.assert_called_once_with(mock_formatter)

        # Verify the handler was added to the exosphere logger
        mock_logger.assert_called_with("exosphere")
        mock_exosphere_logger.addHandler.assert_called_once_with(mock_handler_instance)

        # Verify switch_mode was called with dashboard
        mock_switch_mode.assert_called_once_with("dashboard")

        # Verify the handler was assigned to the app
        assert app.ui_log_handler == mock_handler_instance

    def test_on_unmount_cleans_up_handler(self, app, mock_logger, mocker):
        """Test that on_unmount properly cleans up the log handler."""
        # Set up a mock handler
        mock_handler = mocker.Mock(spec=UILogHandler)
        app.ui_log_handler = mock_handler

        # Mock the exosphere logger
        mock_exosphere_logger = mocker.Mock()
        mock_logger.return_value = mock_exosphere_logger

        # Call on_unmount
        app.on_unmount()

        # Verify the handler was removed from the logger
        mock_logger.assert_called_with("exosphere")
        mock_exosphere_logger.removeHandler.assert_called_once_with(mock_handler)

        # Verify the handler was closed
        mock_handler.close.assert_called_once()

        # Verify the handler was set to None
        assert app.ui_log_handler is None

    def test_on_unmount_with_no_handler(self, app, mock_logger, mocker):
        """Test that on_unmount handles case when ui_log_handler is None."""
        # Ensure handler is None
        app.ui_log_handler = None

        # Mock the exosphere logger
        mock_exosphere_logger = mocker.Mock()
        mock_logger.return_value = mock_exosphere_logger

        # Call on_unmount (should not raise any exceptions)
        app.on_unmount()

        # Verify logger methods were not called since handler was None
        mock_exosphere_logger.removeHandler.assert_not_called()

    def test_app_has_required_methods(self, app):
        """Test that the app has all required methods and they are callable."""
        # Test class structure
        assert isinstance(app, ExosphereUi)

        # The important methods for the main app
        required_methods = [
            "compose",
            "on_mount",
            "on_unmount",
            "on_host_status_changed",
        ]

        for method_name in required_methods:
            assert hasattr(app, method_name), f"Missing method: {method_name}"
            assert callable(getattr(app, method_name)), (
                f"Method not callable: {method_name}"
            )

    def test_screen_modes_are_screen_classes(self, app):
        """Test that all MODES values are valid screen classes."""
        for mode_name, screen_class in app.MODES.items():
            # Check that it's a class and likely inherits from Screen
            assert isinstance(screen_class, type)
            assert hasattr(screen_class, "__name__")

            # Test specific screen classes
            if mode_name == "dashboard":
                assert screen_class.__name__ == "DashboardScreen"
            elif mode_name == "inventory":
                assert screen_class.__name__ == "InventoryScreen"
            elif mode_name == "logs":
                assert screen_class.__name__ == "LogsScreen"

    def test_on_unmount_basic_flow(self, app, mock_logger, mocker):
        """Test basic flow of on_unmount."""
        # Set up a mock handler
        mock_handler = mocker.Mock(spec=UILogHandler)
        app.ui_log_handler = mock_handler
        mock_exosphere_logger = mocker.Mock()
        mock_logger.return_value = mock_exosphere_logger

        # Call on_unmount
        app.on_unmount()

        # Verify cleanup was performed
        mock_exosphere_logger.removeHandler.assert_called_once_with(mock_handler)
        mock_handler.close.assert_called_once()
        assert app.ui_log_handler is None

    def test_handler_cleanup_when_none(self, app, mock_logger, mocker):
        """Test that on_unmount handles None handler gracefully."""
        app.ui_log_handler = None
        mock_exosphere_logger = mocker.Mock()
        mock_logger.return_value = mock_exosphere_logger

        # Should not raise any exceptions
        app.on_unmount()

        # Logger methods should not be called since handler is None
        mock_exosphere_logger.removeHandler.assert_not_called()

    def test_on_host_status_changed_calls_flag_screen_dirty_except(
        self, app, mock_screenflags, mocker
    ):
        """Test that on_host_status_changed calls flag_screen_dirty_except with the message's current_screen."""
        # Set up registered screens
        mock_screenflags.registered_screens = ["dashboard", "inventory"]

        # Create message
        message = HostStatusChanged("dashboard")

        # Run the async method
        asyncio.run(app.on_host_status_changed(message))

        # Verify flag_screen_dirty_except was called with the correct screen
        mock_screenflags.flag_screen_dirty_except.assert_called_once_with("dashboard")

    def test_on_host_status_changed_with_unregistered_screen(
        self, app, mock_screenflags, caplog
    ):
        """
        Test that on_host_status_changed emits warning for unregistered screens
            and still calls flag_screen_dirty_except.
        """
        # Set up registered screens (not including the sender)
        mock_screenflags.registered_screens = ["inventory", "logs"]

        # Create message from unregistered screen
        message = HostStatusChanged("unknown_screen")

        # Capture logs at WARNING level to verify the warning is emitted
        with caplog.at_level(logging.WARNING):
            # Run the async method
            asyncio.run(app.on_host_status_changed(message))

        # Verify flag_screen_dirty_except was still called, even for unregistered screen
        mock_screenflags.flag_screen_dirty_except.assert_called_once_with(
            "unknown_screen"
        )

        # Verify warning was logged for unregistered screen
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        assert (
            "Received host status change from unregistered screen: unknown_screen"
            in caplog.records[0].message
        )

    def test_on_host_status_changed_with_registered_screen_no_warning(
        self, app, mock_screenflags, caplog
    ):
        """Test that on_host_status_changed does NOT emit warning for registered screens."""
        # Set up registered screens (including the sender)
        mock_screenflags.registered_screens = ["dashboard", "inventory", "logs"]

        # Create message from registered screen
        message = HostStatusChanged("dashboard")

        # Capture logs at WARNING level to verify no warning is emitted
        with caplog.at_level(logging.WARNING):
            # Run the async method
            asyncio.run(app.on_host_status_changed(message))

        # Verify flag_screen_dirty_except was called
        mock_screenflags.flag_screen_dirty_except.assert_called_once_with("dashboard")

        # Verify NO warning was logged for registered screen
        warning_records = [
            record for record in caplog.records if record.levelname == "WARNING"
        ]
        assert len(warning_records) == 0
