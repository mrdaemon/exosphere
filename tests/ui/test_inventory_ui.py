"""
Tests for the Inventory Screen UI

Tests the InventoryScreen class, including filtering functionality,
table population, and user interactions.

As with most of the UI tests, these are absolutely awful and only vaguely
useful since Textual's helpers require full asyncio, and I am not ready to
accept it into my heart just yet.
"""

import pytest
from textual.widgets import DataTable

from exosphere import context
from exosphere.data import Update
from exosphere.objects import Host
from exosphere.ui.inventory import FilterMode, FilterScreen, InventoryScreen


@pytest.fixture
def mock_inventory(mocker):
    """
    Create a mock inventory with test hosts.
    """
    inventory = mocker.Mock()

    # Create real Update objects for testing
    update1 = Update(
        name="kernel",
        current_version="5.14.0",
        new_version="5.15.0",
        security=True,
        source="updates",
    )
    update2 = Update(
        name="bash",
        current_version="5.1",
        new_version="5.2",
        security=False,
        source="updates",
    )
    update3 = Update(
        name="openssl",
        current_version="3.0.0",
        new_version="3.0.7",
        security=True,
        source="updates",
    )

    # Create a series of mock hosts with pre-populated data.
    # This is super brittle and will ruin christmas the second
    # the Host class changes, but it will do for now.
    host1 = mocker.Mock(spec=Host)
    host1.name = "testserver1"
    host1.ip = "127.0.0.1"
    host1.port = 22
    host1.os = "linux"
    host1.flavor = "rhel"
    host1.version = "9.3"
    host1.description = "Production server"
    host1.online = True
    host1.supported = True
    host1.updates = [update1, update2]  # 2 updates
    host1.security_updates = [update1]  # 1 security update
    host1.is_stale = False
    host1.last_refresh = mocker.Mock()

    host2 = mocker.Mock(spec=Host)
    host2.name = "testserver2"
    host2.ip = "127.0.0.2"
    host2.port = 22
    host2.os = "linux"
    host2.flavor = "debian"
    host2.version = "12"
    host2.description = "Test server"
    host2.online = True
    host2.supported = True
    host2.updates = []  # No updates
    host2.security_updates = []
    host2.is_stale = False
    host2.last_refresh = mocker.Mock()

    host3 = mocker.Mock(spec=Host)
    host3.name = "testserver3"
    host3.ip = "127.0.0.3"
    host3.port = 22
    host3.os = "freebsd"
    host3.flavor = "freebsd"
    host3.version = "14.0"
    host3.description = None
    host3.online = False
    host3.supported = True
    host3.updates = [update3]  # 1 update
    host3.security_updates = [update3]  # 1 security update
    host3.is_stale = True
    host3.last_refresh = mocker.Mock()

    inventory.hosts = [host1, host2, host3]
    inventory.get_host = lambda name: next(
        (h for h in inventory.hosts if h.name == name), None
    )

    return inventory


@pytest.fixture
def inventory_screen():
    """
    Create an InventoryScreen instance for testing.
    """
    return InventoryScreen()


@pytest.fixture
def setup_inventory_mock(mock_inventory, mocker):
    """
    Setup the global context with mock inventory.
    """
    mocker.patch.object(context, "inventory", mock_inventory)
    return mock_inventory


class TestInventoryScreenInitialization:
    """Test InventoryScreen initialization and basic setup."""

    def test_screen_initialization(self, inventory_screen):
        """
        Test that InventoryScreen initializes with correct defaults.
        """
        assert isinstance(inventory_screen, InventoryScreen)
        assert inventory_screen.current_filter == FilterMode.NONE

    def test_screen_has_bindings(self, inventory_screen):
        """
        Test that screen has expected key bindings.
        (Somewhat. We don't know if they work.)
        """
        from textual.binding import Binding

        bindings = []
        for b in inventory_screen.BINDINGS:
            if isinstance(b, Binding):
                bindings.append(b.key)
            else:
                bindings.append(b[0])

        assert "ctrl+r" in bindings
        assert "ctrl+x" in bindings
        assert "ctrl+f" in bindings


class TestFilteringLogic:
    """Test the filtering logic and get_filtered_hosts method."""

    def test_get_filtered_hosts_none(self, inventory_screen, setup_inventory_mock):
        """
        Test that NONE filter returns all hosts.
        """
        inventory_screen.current_filter = FilterMode.NONE
        hosts = inventory_screen.get_filtered_hosts()

        assert len(hosts) == 3
        assert hosts[0].name == "testserver1"
        assert hosts[1].name == "testserver2"
        assert hosts[2].name == "testserver3"

    def test_get_filtered_hosts_updates_only(
        self, inventory_screen, setup_inventory_mock
    ):
        """
        Test that UPDATES_ONLY filter returns only hosts with updates.
        """
        inventory_screen.current_filter = FilterMode.UPDATES_ONLY
        hosts = inventory_screen.get_filtered_hosts()

        # Should return host1 (2 updates) and host3 (1 update), but not host2 (no updates)
        assert len(hosts) == 2
        assert hosts[0].name == "testserver1"
        assert hosts[1].name == "testserver3"

    def test_get_filtered_hosts_security_only(
        self, inventory_screen, setup_inventory_mock
    ):
        """
        Test that SECURITY_ONLY filter returns only hosts with security updates.
        """
        inventory_screen.current_filter = FilterMode.SECURITY_ONLY
        hosts = inventory_screen.get_filtered_hosts()

        # Should return host1 and host3 (both have security updates), not host2
        assert len(hosts) == 2
        assert hosts[0].name == "testserver1"
        assert hosts[1].name == "testserver3"

    def test_get_filtered_hosts_no_inventory(self, inventory_screen, mocker):
        """
        Test that get_filtered_hosts handles missing inventory gracefully.
        """
        mocker.patch.object(context, "inventory", None)
        hosts = inventory_screen.get_filtered_hosts()

        assert hosts == []

    def test_get_filtered_hosts_empty_inventory(self, inventory_screen, mocker):
        """
        Test filtering with empty inventory.
        PRACTICALLY: The UI will handle this and avoid the codepath entirely,
        but we should still handle it gracefully.
        """
        mock_empty = mocker.Mock()
        mock_empty.hosts = []
        mocker.patch.object(context, "inventory", mock_empty)

        inventory_screen.current_filter = FilterMode.UPDATES_ONLY
        hosts = inventory_screen.get_filtered_hosts()

        assert hosts == []


class TestActionFilterView:
    """Test the action_filter_view method and filter selection."""

    def test_action_filter_view_opens_filter_screen(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that action_filter_view pushes FilterScreen.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        inventory_screen.action_filter_view()

        # Verify FilterScreen was pushed
        mock_app.push_screen.assert_called_once()
        args = mock_app.push_screen.call_args[0]
        assert isinstance(args[0], FilterScreen)
        # Second arg should be the callback
        assert callable(args[1])

    def test_action_filter_view_no_hosts(self, inventory_screen, mocker):
        """
        Test that action_filter_view shows error when no hosts available.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )
        mocker.patch.object(context, "inventory", None)

        inventory_screen.action_filter_view()

        # Should push ErrorScreen instead of FilterScreen
        mock_app.push_screen.assert_called_once()
        from exosphere.ui.elements import ErrorScreen

        args = mock_app.push_screen.call_args[0]
        assert isinstance(args[0], ErrorScreen)

    def test_filter_selection_callback_updates_filter(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that selecting a filter updates current_filter and refreshes.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        # Mock only refresh_rows, let label update happen naturally
        mock_refresh = mocker.patch.object(inventory_screen, "refresh_rows")
        mock_filter_label = mocker.Mock()
        mocker.patch.object(
            inventory_screen, "query_one", return_value=mock_filter_label
        )

        # Call action_filter_view to get the callback
        inventory_screen.action_filter_view()
        callback = mock_app.push_screen.call_args[0][1]

        # Simulate filter selection
        callback(FilterMode.UPDATES_ONLY)

        # Verify state was updated
        assert inventory_screen.current_filter == FilterMode.UPDATES_ONLY

        # Verify refresh was called
        mock_refresh.assert_called_once_with("filter")

        # Verify filter label was updated with correct text
        mock_filter_label.update.assert_called_once()
        label_text = mock_filter_label.update.call_args[0][0]
        assert f"Filtered: {FilterMode.UPDATES_ONLY}" in label_text

    def test_filter_selection_security_updates_label(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that selecting security filter updates label correctly.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        mocker.patch.object(inventory_screen, "refresh_rows")  # Avoid side effects
        mock_filter_label = mocker.Mock()
        mocker.patch.object(
            inventory_screen, "query_one", return_value=mock_filter_label
        )

        inventory_screen.action_filter_view()
        callback = mock_app.push_screen.call_args[0][1]

        # Simulate security filter selection
        callback(FilterMode.SECURITY_ONLY)

        # Verify filter label shows security filter text
        label_text = mock_filter_label.update.call_args[0][0]
        assert f"Filtered: {FilterMode.SECURITY_ONLY}" in label_text

    def test_filter_selection_none_shows_base_label(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that NONE filter clears the filter label.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        mocker.patch.object(inventory_screen, "refresh_rows")  # Avoid side effects
        mock_filter_label = mocker.Mock()
        mocker.patch.object(
            inventory_screen, "query_one", return_value=mock_filter_label
        )

        # Set a filter first
        inventory_screen.current_filter = FilterMode.UPDATES_ONLY

        inventory_screen.action_filter_view()
        callback = mock_app.push_screen.call_args[0][1]

        # Clear filter back to NONE
        callback(FilterMode.NONE)

        # Verify filter label is cleared (empty string)
        label_text = mock_filter_label.update.call_args[0][0]
        assert label_text == ""

    def test_filter_selection_callback_none_does_nothing(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that callback with None (cancel) doesn't change filter.
        """
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )
        original_filter = inventory_screen.current_filter

        mock_refresh = mocker.patch.object(inventory_screen, "refresh_rows")

        # Call action_filter_view to get the callback
        inventory_screen.action_filter_view()
        callback = mock_app.push_screen.call_args[0][1]

        # Simulate cancellation (None)
        callback(None)

        # Verify filter was not changed
        assert inventory_screen.current_filter == original_filter

        # Verify refresh was not called
        mock_refresh.assert_not_called()


class TestRefreshRows:
    """Test the refresh_rows method."""

    def test_refresh_rows_clears_and_repopulates(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that refresh_rows clears table and repopulates with correct data.
        """
        mock_table = mocker.Mock(spec=DataTable)
        mocker.patch.object(inventory_screen, "query_one", return_value=mock_table)
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        inventory_screen.refresh_rows()

        # Should clear table (but keep columns)
        mock_table.clear.assert_called_once_with(columns=False)

        # Should add rows for all hosts (3 total)
        assert mock_table.add_row.call_count == 3

        # Should notify
        mock_app.notify.assert_called_once()

    def test_refresh_rows_with_filter(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that refresh_rows uses filtered hosts and populates correct data.
        """
        mock_table = mocker.Mock(spec=DataTable)
        mocker.patch.object(inventory_screen, "query_one", return_value=mock_table)
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        # Set filter to updates only
        inventory_screen.current_filter = FilterMode.UPDATES_ONLY
        inventory_screen.refresh_rows("filter")

        # Should only add 2 rows (hosts with updates)
        assert mock_table.add_row.call_count == 2

    def test_refresh_rows_formats_stale_indicator(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test that refresh_rows formats stale hosts with asterisk indicator.
        """
        mock_table = mocker.Mock(spec=DataTable)
        mocker.patch.object(inventory_screen, "query_one", return_value=mock_table)
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        inventory_screen.refresh_rows()

        # Get the third host (server3) which is stale
        third_call = mock_table.add_row.call_args_list[2]
        row_data = third_call[0]

        # Updates column should have stale indicator
        updates_col = row_data[4]  # 5th column (0-indexed)
        assert "*" in updates_col  # Stale indicator

    def test_refresh_rows_no_matching_hosts(
        self, inventory_screen, setup_inventory_mock, mocker
    ):
        """
        Test refresh_rows when no hosts match filter.
        """
        mock_table = mocker.Mock(spec=DataTable)
        mocker.patch.object(inventory_screen, "query_one", return_value=mock_table)
        mock_app = mocker.Mock()
        mocker.patch.object(
            type(inventory_screen),
            "app",
            new_callable=mocker.PropertyMock,
            return_value=mock_app,
        )

        # Create inventory with no security updates
        mock_inv = mocker.Mock()
        host = mocker.Mock(spec=Host)
        host.supported = True
        host.updates = []
        host.security_updates = []
        mock_inv.hosts = [host]
        mocker.patch.object(context, "inventory", mock_inv)

        # Set filter to security only
        inventory_screen.current_filter = FilterMode.SECURITY_ONLY
        inventory_screen.refresh_rows()

        # Should clear table
        mock_table.clear.assert_called_once_with(columns=False)

        # Should notify with error severity
        assert mock_app.notify.call_count == 1
        notify_kwargs = mock_app.notify.call_args[1]
        assert notify_kwargs.get("severity") == "error"
