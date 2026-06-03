import pytest
from textual.widgets import Footer, Header

from exosphere.inventory import HostOperation
from exosphere.ui.app import ExosphereUi
from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.elements import DataScreen, ErrorScreen, ProgressScreen, TaskOutcome
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen, UILogHandler


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

        # Mock the RichLogFormatter
        mock_formatter = mocker.Mock()
        mocker.patch("exosphere.ui.app.RichLogFormatter", return_value=mock_formatter)

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
            "run_host_task",
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

    @pytest.fixture
    def mock_context(self, mocker):
        """Mock the app's context module to control inventory state."""
        return mocker.patch("exosphere.ui.app.context")

    def test_run_host_task_no_inventory_pushes_error(self, app, mocker, mock_context):
        """run_host_task pushes an ErrorScreen when inventory is uninitialized."""
        mock_context.inventory = None
        push = mocker.patch.object(app, "push_screen")

        app.run_host_task(HostOperation.PING, message="m", no_hosts_message="nh")

        push.assert_called_once()
        pushed = push.call_args[0][0]
        assert isinstance(pushed, ErrorScreen)
        assert "not initialized" in pushed.message.lower()

    def test_run_host_task_no_hosts_pushes_error(self, app, mocker, mock_context):
        """run_host_task pushes an ErrorScreen with the no_hosts message."""
        mock_context.inventory = mocker.Mock(hosts=[])
        push = mocker.patch.object(app, "push_screen")

        app.run_host_task(
            HostOperation.PING, message="m", no_hosts_message="No hosts here!"
        )

        push.assert_called_once()
        pushed = push.call_args[0][0]
        assert isinstance(pushed, ErrorScreen)
        assert pushed.message == "No hosts here!"

    def test_run_host_task_pushes_progress_screen(self, app, mocker, mock_context):
        """run_host_task pushes a ProgressScreen carrying the operation."""
        host = mocker.Mock()
        mock_context.inventory = mocker.Mock(hosts=[host])
        push = mocker.patch.object(app, "push_screen")

        app.run_host_task(
            HostOperation.REFRESH, message="Refreshing", no_hosts_message="nh"
        )

        push.assert_called_once()
        pushed = push.call_args[0][0]
        assert isinstance(pushed, ProgressScreen)
        assert pushed.operation is HostOperation.REFRESH
        assert pushed.message == "Refreshing"
        assert pushed.hosts == [host]

    def test_run_host_task_uses_host_subset(self, app, mocker, mock_context):
        """An explicit hosts subset is dispatched instead of all hosts."""
        h1, h2, h3 = mocker.Mock(), mocker.Mock(), mocker.Mock()
        mock_context.inventory = mocker.Mock(hosts=[h1, h2, h3])
        push = mocker.patch.object(app, "push_screen")

        app.run_host_task(
            HostOperation.PING, hosts=[h2], message="m", no_hosts_message="nh"
        )

        pushed = push.call_args[0][0]
        assert pushed.hosts == [h2]

    def test_run_host_task_invokes_custom_callback_on_complete(
        self, app, mocker, mock_context
    ):
        """The custom callback runs when the ProgressScreen completes."""
        mock_context.inventory = mocker.Mock(hosts=[mocker.Mock()])
        push = mocker.patch.object(app, "push_screen")
        custom = mocker.Mock()

        app.run_host_task(
            HostOperation.PING, message="m", no_hosts_message="nh", callback=custom
        )

        # push_screen gets a wrapper; invoking it with an outcome runs the
        # custom callback (after rendering feedback).
        on_complete = push.call_args[0][1]
        outcome = TaskOutcome(operation=HostOperation.PING, host_count=1)
        on_complete(outcome)

        custom.assert_called_once_with(outcome)

    def test_run_host_task_forwards_report_result(self, app, mocker, mock_context):
        """report_result is forwarded to the ProgressScreen."""
        mock_context.inventory = mocker.Mock(hosts=[mocker.Mock()])
        push = mocker.patch.object(app, "push_screen")

        app.run_host_task(
            HostOperation.REFRESH,
            message="a message",
            no_hosts_message="no boys here",
            report_result=False,
        )

        assert push.call_args[0][0].report_result is False

    def test_run_host_operation_targets_single_host(self, app, mocker):
        """run_host_operation dispatches the op against just the one host."""
        run_task = mocker.patch.object(app, "run_host_task")
        host = mocker.Mock()
        host.name = "web1"

        app.run_host_operation(HostOperation.REFRESH, host)

        run_task.assert_called_once()
        kwargs = run_task.call_args.kwargs
        assert kwargs["operation"] is HostOperation.REFRESH
        assert kwargs["hosts"] == [host]

    def test_run_host_sync_refresh_chains_sync_then_refresh(self, app, mocker):
        """Sync runs first (quiet) with a callback that triggers refresh."""
        run_task = mocker.patch.object(app, "run_host_task")
        host = mocker.Mock()
        host.name = "web1"

        app.run_host_sync_refresh(host)

        # First dispatch is the sync, intermediate (no result reporting).
        run_task.assert_called_once()
        sync_kwargs = run_task.call_args.kwargs
        assert sync_kwargs["operation"] is HostOperation.SYNC
        assert sync_kwargs["hosts"] == [host]
        assert sync_kwargs["report_result"] is False

        # Invoking the sync callback triggers the refresh step.
        sync_kwargs["callback"](None)

        assert run_task.call_count == 2
        refresh_kwargs = run_task.call_args.kwargs
        assert refresh_kwargs["operation"] is HostOperation.REFRESH
        assert refresh_kwargs["hosts"] == [host]

    def test_run_host_operation_all_targets_all_hosts(self, app, mocker):
        """run_host_operation_all dispatches with no host subset (all hosts)."""
        run_task = mocker.patch.object(app, "run_host_task")

        app.run_host_operation_all(HostOperation.PING)

        run_task.assert_called_once()
        kwargs = run_task.call_args.kwargs
        assert kwargs["operation"] is HostOperation.PING
        assert "hosts" not in kwargs or kwargs["hosts"] is None

    def test_run_sync_refresh_all_chains_sync_then_refresh(self, app, mocker):
        """The all-hosts sync runs first with a callback that refreshes all."""
        run_task = mocker.patch.object(app, "run_host_task")

        app.run_sync_refresh_all()

        run_task.assert_called_once()
        sync_kwargs = run_task.call_args.kwargs
        assert sync_kwargs["operation"] is HostOperation.SYNC
        assert sync_kwargs["report_result"] is False

        sync_kwargs["callback"](None)

        assert run_task.call_count == 2
        assert run_task.call_args.kwargs["operation"] is HostOperation.REFRESH

    def test_success_message(self, app, mocker):
        """Ping reports Online/Offline; other ops report completion."""
        host = mocker.Mock()
        host.name = "web1"
        assert app._success_message(HostOperation.PING, host, True) == "web1 is Online"
        assert (
            app._success_message(HostOperation.PING, host, False) == "web1 is Offline"
        )
        assert (
            app._success_message(HostOperation.REFRESH, host, None)
            == "Refresh Updates complete on web1"
        )

    def test_render_feedback_single_host_success_notifies(self, app, mocker):
        """A single-host success surfaces a result notification."""
        notify = mocker.patch.object(app, "notify")
        host = mocker.Mock()
        host.name = "web1"

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.REFRESH,
                results=[(host, None, None)],
                host_count=1,
            )
        )

        notify.assert_called_once()
        assert "Refresh Updates complete on web1" in notify.call_args[0][0]

    def test_render_feedback_single_host_failure_pushes_error(self, app, mocker):
        """A single-host failure pushes a titled ErrorScreen with the exception."""
        push = mocker.patch.object(app, "push_screen")
        host = mocker.Mock()
        host.name = "web1"

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.REFRESH,
                results=[(host, None, RuntimeError("boom"))],
                exc_count=1,
                host_count=1,
            )
        )

        push.assert_called_once()
        screen = push.call_args[0][0]
        assert isinstance(screen, ErrorScreen)
        assert "Refresh Updates failed on web1" in screen.message
        assert "boom" in screen.message

    def test_render_feedback_bulk_errors_notify_only(self, app, mocker):
        """Bulk errors get an aggregate notify, no modal."""
        notify = mocker.patch.object(app, "notify")
        push = mocker.patch.object(app, "push_screen")
        h1, h2 = mocker.Mock(), mocker.Mock()

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.REFRESH,
                results=[(h1, None, None), (h2, None, RuntimeError())],
                exc_count=1,
                host_count=2,
            )
        )

        push.assert_not_called()
        assert "1 error" in notify.call_args[0][0]

    def test_render_feedback_report_result_false_falls_back_to_aggregate(
        self, app, mocker
    ):
        """With report_result False, even a single host uses the aggregate path."""
        notify = mocker.patch.object(app, "notify")
        push = mocker.patch.object(app, "push_screen")
        host = mocker.Mock()
        host.name = "web1"

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.SYNC,
                results=[(host, None, RuntimeError("x"))],
                exc_count=1,
                host_count=1,
                report_result=False,
            )
        )

        push.assert_not_called()  # no modal for the intermediate step
        assert "1 error" in notify.call_args[0][0]

    def test_render_feedback_cancelled_notifies(self, app, mocker):
        """A cancelled task notifies and renders nothing else."""
        notify = mocker.patch.object(app, "notify")
        push = mocker.patch.object(app, "push_screen")

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.REFRESH, was_cancelled=True, host_count=1
            )
        )

        push.assert_not_called()
        assert "cancelled" in notify.call_args[0][0].lower()

    def test_render_feedback_save_error_pushes_error(self, app, mocker):
        """A save failure surfaces an ErrorScreen."""
        push = mocker.patch.object(app, "push_screen")

        app._render_task_feedback(
            TaskOutcome(
                operation=HostOperation.REFRESH,
                save_error=RuntimeError("disk full"),
                host_count=1,
            )
        )

        push.assert_called_once()
        assert "disk full" in push.call_args[0][0].message

    def test_after_task_refreshes_active_data_screen(
        self, app, mocker, mock_screenflags
    ):
        """Default callback refreshes the active data screen, flags the rest."""
        mock_screenflags.registered_screens = ["dashboard", "inventory"]

        screen = mocker.Mock(spec=DataScreen)
        screen.get_screen_name.return_value = "inventory"
        mocker.patch.object(
            type(app), "screen", new_callable=mocker.PropertyMock, return_value=screen
        )

        app._after_task(HostOperation.REFRESH)(None)

        # Notification should not be sent when from active screen
        screen.refresh_data_after_task.assert_called_once_with(
            "refresh_updates", notify=False
        )
        mock_screenflags.flag_screen_dirty_except.assert_called_once_with("inventory")
        mock_screenflags.flag_screen_dirty.assert_not_called()

    def test_after_task_from_non_data_screen_flags_all(
        self, app, mocker, mock_screenflags
    ):
        """When the active screen is not a data screen, flag all data screens."""
        mock_screenflags.registered_screens = ["dashboard", "inventory"]

        # We sub out the active screen with a plain Mock
        # Which is definitely not a DataScreen.
        screen = mocker.Mock()
        mocker.patch.object(
            type(app), "screen", new_callable=mocker.PropertyMock, return_value=screen
        )

        app._after_task(HostOperation.PING)(None)

        mock_screenflags.flag_screen_dirty.assert_called_once_with(
            "dashboard", "inventory"
        )
        mock_screenflags.flag_screen_dirty_except.assert_not_called()
