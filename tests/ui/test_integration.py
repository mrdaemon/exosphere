"""
Integration tests for the Text User Interface (TUI) screens.

This test suite should detect General Issues with any of the UI screen.
They mostly serve as smoke tests to catch errors during screen composition.

They _actually_ use the Textual testing framework, unlike the rest of the
stupid tests in this project.

Tests are marked with @pytest.mark.asyncio to enable async test execution,
which is done explicitly because I want to contain asyncio to its own
awful little corner of hell instead of spreading it everywhere.
"""

import pytest

from exosphere.ui.app import ExosphereUi
from exosphere.ui.dashboard import DashboardScreen
from exosphere.ui.elements import ErrorScreen
from exosphere.ui.inventory import InventoryScreen
from exosphere.ui.logs import LogsScreen


@pytest.mark.asyncio
async def test_app_starts_and_shows_dashboard():
    """
    Test that the app starts successfully and displays the dashboard.

    This is a smoke test that verifies the app can be instantiated
    and the initial screen (dashboard) can be composed without errors.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # App should start on dashboard
        assert isinstance(app.screen, DashboardScreen)

        # Give it a moment to settle
        await pilot.pause()


@pytest.mark.asyncio
async def test_navigate_to_inventory_screen():
    """
    Test navigation to the inventory screen (key: i).

    This test ensures the InventoryScreen can be composed and displayed,
    which would catch issues like Footer(compact=True) with incompatible
    Textual versions.

    This very regression is what prompted this entire test suite.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # Navigate to inventory screen
        await pilot.press("i")
        await pilot.pause()

        # Should be on inventory screen
        assert isinstance(app.screen, InventoryScreen)


@pytest.mark.asyncio
async def test_navigate_to_logs_screen():
    """
    Test navigation to the logs screen (key: l).

    Verifies the LogsScreen can be composed and displayed.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # Navigate to logs screen
        await pilot.press("l")
        await pilot.pause()

        # Should be on logs screen
        assert isinstance(app.screen, LogsScreen)


@pytest.mark.asyncio
async def test_navigate_between_all_screens():
    """
    Test navigation flow between dashboard, inventory, and logs.

    A final smoke tests that comprehensively tests all of the screen
    in one single run, to ensure no state garbage causes issues.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # Start on dashboard
        assert isinstance(app.screen, DashboardScreen)
        await pilot.pause()

        # Go to inventory
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, InventoryScreen)

        # Go to logs
        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, LogsScreen)

        # Back to dashboard
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)

        # Back to inventory to ensure we can navigate again
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, InventoryScreen)


@pytest.mark.asyncio
async def test_app_quit():
    """
    Test that the app can quit successfully (key: Ctrl+Q).

    This test ensures that the application can handle the quit
    command without errors.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # Quit the app
        await pilot.press("ctrl+q")
        await pilot.pause()

        # The app should be in the process of shutting down
        assert app.is_running is False


@pytest.mark.asyncio
async def test_error_screen_display_and_dismiss():
    """
    Test that ErrorScreen can be displayed and dismissed.

    This test verifies that an ErrorScreen can be pushed onto the stack,
    displays correctly, and can be dismissed by pressing the OK button.
    """
    app = ExosphereUi()
    async with app.run_test() as pilot:
        # Push an error screen
        error_message = "Test error message"
        error_screen = ErrorScreen(error_message)
        app.push_screen(error_screen)
        await pilot.pause()

        # Verify we're on the error screen
        assert isinstance(app.screen, ErrorScreen)
        assert app.screen.message == error_message

        # Press Enter to activate the OK button (or click it)
        # The OK button should be focused by default in most cases
        await pilot.press("enter")
        await pilot.pause()

        # Should be back on dashboard after dismissing error
        assert isinstance(app.screen, DashboardScreen)
