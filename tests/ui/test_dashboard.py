import pytest

from exosphere.objects import Host
from exosphere.ui.dashboard import DashboardScreen, HostWidget
from exosphere.ui.messages import HostStatusChanged


@pytest.fixture
def host_online():
    host = Host(name="host1", ip="127.0.0.2", description="Test host")
    host.online = True
    host.flavor = "Ubuntu"
    host.version = "22.04"
    return host


@pytest.fixture
def host_offline():
    host = Host(name="host2", ip="127.0.0.3", description=None)
    host.online = False
    host.flavor = "Debian"
    host.version = "11"
    return host


@pytest.fixture
def host_undiscovered():
    host = Host(name="host3", ip="127.0.0.4", description=None)
    host.online = False
    host.flavor = None
    host.version = None
    return host


@pytest.fixture
def mock_inventory(mocker):
    """Create a mock inventory for testing."""
    inventory = mocker.MagicMock()
    inventory.hosts = []
    return inventory


@pytest.fixture
def mock_context(mocker, mock_inventory):
    """Mock the context module."""
    mock_context = mocker.patch("exosphere.ui.dashboard.context")
    mock_context.inventory = mock_inventory
    return mock_context


@pytest.fixture
def mock_app(mocker):
    """Create a mock app for testing."""
    app = mocker.MagicMock()
    return app


@pytest.fixture
def mock_label(mocker):
    """Create a mock Label widget."""
    return mocker.MagicMock()


def test_hostwidget_compose_online(host_online, mocker):
    """Test that HostWidget composes correctly for an online host."""
    # Mock Container and Label to avoid app context issues
    mock_container = mocker.MagicMock()
    mock_label = mocker.MagicMock()

    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    label_mock = mocker.patch("exosphere.ui.dashboard.Label", return_value=mock_label)

    widget = HostWidget(host_online)
    result = list(widget.compose())

    # Should yield 4 labels: name, version, description, status
    assert len(result) == 4

    # Verify Label calls - should be 4 labels: name, version, description, status
    assert label_mock.call_count == 4

    # Check the calls for expected content and classes
    calls = label_mock.call_args_list
    assert calls[0][0][0] == "[b]host1[/b]"  # name
    assert calls[0][1]["classes"] == "host-name"

    assert "Ubuntu 22.04" in calls[1][0][0]  # version
    assert calls[1][1]["classes"] == "host-version"

    assert calls[2][0][0] == "Test host"  # description
    assert calls[2][1]["classes"] == "host-description"

    assert "[green]Online[/green]" in calls[3][0][0]  # status
    assert calls[3][1]["classes"] == "host-status"


def test_hostwidget_compose_offline(host_offline, mocker):
    """Test that HostWidget composes correctly for an offline host."""
    # Mock Container and Label to avoid app context issues
    mock_container = mocker.MagicMock()
    mock_label = mocker.MagicMock()

    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    label_mock = mocker.patch("exosphere.ui.dashboard.Label", return_value=mock_label)

    widget = HostWidget(host_offline)
    result = list(widget.compose())

    # Should yield 4 labels: name, version, description (empty), status
    assert len(result) == 4

    # Verify Label calls - should be 4 labels: name, version, description (empty), status
    assert label_mock.call_count == 4

    # Check the calls for expected content and classes
    calls = label_mock.call_args_list
    assert calls[0][0][0] == "[b]host2[/b]"  # name
    assert "Debian 11" in calls[1][0][0]  # version
    assert calls[2][0][0] == ""  # description (empty)
    assert calls[2][1]["classes"] == "host-description"
    assert "[red]Offline[/red]" in calls[3][0][0]  # status


def test_hostwidget_compose_offline_undiscovered(host_undiscovered, mocker):
    """Test that HostWidget composes correctly for an undiscovered host."""
    # Mock Container and Label to avoid app context issues
    mock_container = mocker.MagicMock()
    mock_label = mocker.MagicMock()

    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    label_mock = mocker.patch("exosphere.ui.dashboard.Label", return_value=mock_label)

    widget = HostWidget(host_undiscovered)
    result = list(widget.compose())

    # Should yield 4 labels: name, version, description (empty), status
    assert len(result) == 4

    # Verify Label calls - should be 4 labels: name, version, description (empty), status
    assert label_mock.call_count == 4

    # Check the calls for expected content and classes
    calls = label_mock.call_args_list
    assert calls[0][0][0] == "[b]host3[/b]"  # name
    assert "(Undiscovered)" in calls[1][0][0]  # version
    assert calls[2][0][0] == ""  # description (empty)
    assert "[red]Offline[/red]" in calls[3][0][0]  # status


def test_hostwidget_init():
    """Test HostWidget initialization."""
    host = Host(name="test", ip="127.0.0.1")
    widget = HostWidget(host, id="test-widget")
    assert widget.host == host
    assert widget.id == "test-widget"


def test_hostwidget_refresh_state(mocker, host_online):
    """Test HostWidget refresh_state method."""
    widget = HostWidget(host_online)

    # Mock the query_one method for Container and Labels
    mock_container = mocker.MagicMock()
    mock_status_label = mocker.MagicMock()
    mock_version_label = mocker.MagicMock()

    def query_one_side_effect(selector, widget_type=None):
        if selector == ".host-status":
            return mock_status_label
        elif selector == ".host-version":
            return mock_version_label
        else:  # Container
            return mock_container

    mocker.patch.object(widget, "query_one", side_effect=query_one_side_effect)

    # Initially online
    widget.refresh_state()

    # Check container class changes
    mock_container.add_class.assert_called_with("online")
    mock_container.remove_class.assert_called_with("offline")

    # Check status label update
    mock_status_label.update.assert_called_with("[green]Online[/green]")

    # Check version label update
    mock_version_label.update.assert_called_with("[dim]Ubuntu 22.04[/dim]")

    # Reset mocks and test with offline host
    mock_container.reset_mock()
    mock_status_label.reset_mock()
    mock_version_label.reset_mock()

    widget.host.online = False
    widget.refresh_state()

    # Check container class changes for offline
    mock_container.add_class.assert_called_with("offline")
    mock_container.remove_class.assert_called_with("online")

    # Check status label update for offline
    mock_status_label.update.assert_called_with("[red]Offline[/red]")


def test_dashboard_on_mount_sets_titles(mocker):
    """Test that DashboardScreen sets the correct titles on mount."""

    screen = DashboardScreen()

    mock_update_grid = mocker.patch.object(screen, "update_grid_columns")

    screen.on_mount()

    assert screen.title == "Exosphere"
    assert screen.sub_title == "Dashboard"
    mock_update_grid.assert_called_once()  # Ensure grid columns are updated


def test_dashboard_compose_with_hosts(mock_context, host_online, host_offline, mocker):
    """Test DashboardScreen compose method with hosts."""
    mock_context.inventory.hosts = [host_online, host_offline]

    screen = DashboardScreen()

    # Mock Textual widgets to avoid app context issues
    mock_vertical_scroll = mocker.MagicMock()
    mock_container = mocker.MagicMock()
    mock_host_widget = mocker.MagicMock()

    mocker.patch(
        "exosphere.ui.dashboard.VerticalScroll", return_value=mock_vertical_scroll
    )
    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    host_widget_mock = mocker.patch(
        "exosphere.ui.dashboard.HostWidget", return_value=mock_host_widget
    )

    result = list(screen.compose())

    # Should yield Header, VerticalScroll, and Footer
    assert len(result) >= 3

    # Verify that HostWidget was called twice (once for each host)
    assert host_widget_mock.call_count == 2

    # Verify the hosts passed to HostWidget
    host_widget_calls = host_widget_mock.call_args_list
    assert host_widget_calls[0][0][0] == host_online  # First call with host_online
    assert host_widget_calls[1][0][0] == host_offline  # Second call with host_offline


def test_dashboard_compose_no_hosts(mock_context, mocker):
    """Test DashboardScreen compose method with no hosts shows empty message."""
    mock_context.inventory.hosts = []

    screen = DashboardScreen()

    # Mock Textual widgets to avoid app context issues
    mock_vertical_scroll = mocker.MagicMock()
    mock_container = mocker.MagicMock()
    mock_label = mocker.MagicMock()

    mocker.patch(
        "exosphere.ui.dashboard.VerticalScroll", return_value=mock_vertical_scroll
    )
    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    label_mock = mocker.patch("exosphere.ui.dashboard.Label", return_value=mock_label)

    result = list(screen.compose())

    # Should yield Header, VerticalScroll, and Footer
    assert len(result) >= 3

    # Verify that Label was called with the empty message
    label_mock.assert_called_with("No hosts available.", classes="empty-message")


def test_dashboard_compose_no_inventory(mocker):
    """Test DashboardScreen compose method with no inventory shows empty message."""
    mocker.patch("exosphere.ui.dashboard.context.inventory", None)

    screen = DashboardScreen()

    # Mock Textual widgets to avoid app context issues
    mock_vertical_scroll = mocker.MagicMock()
    mock_container = mocker.MagicMock()
    mock_label = mocker.MagicMock()

    mocker.patch(
        "exosphere.ui.dashboard.VerticalScroll", return_value=mock_vertical_scroll
    )
    mocker.patch("exosphere.ui.dashboard.Container", return_value=mock_container)
    label_mock = mocker.patch("exosphere.ui.dashboard.Label", return_value=mock_label)

    result = list(screen.compose())

    # Should yield Header, VerticalScroll, and Footer
    assert len(result) >= 3

    # Verify that Label was called with the empty message
    label_mock.assert_called_with("No hosts available.", classes="empty-message")


def test_dashboard_refresh_hosts_with_task(mocker, mock_context):
    """Test DashboardScreen refresh_hosts method with task name."""
    screen = DashboardScreen()

    # Mock query and app.notify
    mock_host_widget = mocker.MagicMock()
    mock_query = mocker.patch.object(screen, "query", return_value=[mock_host_widget])
    mock_notify = mocker.MagicMock()

    # Create a mock app that we can control
    mock_app = mocker.MagicMock()
    mock_app.notify = mock_notify

    # Mock the app property by patching the getter
    mocker.patch.object(
        type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
    )

    screen.refresh_hosts("ping")

    mock_query.assert_called_once()
    mock_host_widget.refresh_state.assert_called_once()
    mock_notify.assert_called_once_with(
        "Host data successfully refreshed", title="Refresh Complete"
    )


def test_dashboard_refresh_hosts_without_task(mocker, mock_context):
    """Test DashboardScreen refresh_hosts method without task name."""
    screen = DashboardScreen()

    # Mock query and app.notify
    mock_host_widget = mocker.MagicMock()
    mock_query = mocker.patch.object(screen, "query", return_value=[mock_host_widget])
    mock_notify = mocker.MagicMock()

    # Create a mock app that we can control
    mock_app = mocker.MagicMock()
    mock_app.notify = mock_notify

    # Mock the app property by patching the getter
    mocker.patch.object(
        type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
    )

    screen.refresh_hosts()

    mock_query.assert_called_once()
    mock_host_widget.refresh_state.assert_called_once()
    mock_notify.assert_called_once()


def test_dashboard_action_ping_all_hosts(mocker):
    """Test DashboardScreen action_ping_all_hosts method."""
    screen = DashboardScreen()
    mock_run_task = mocker.patch.object(screen, "_run_task")

    screen.action_ping_all_hosts()

    mock_run_task.assert_called_once_with(
        taskname="ping",
        message="Pinging all hosts...",
        no_hosts_message="No hosts available to ping.",
    )


def test_dashboard_action_discover_hosts(mocker):
    """Test DashboardScreen action_discover_hosts method."""
    screen = DashboardScreen()
    mock_run_task = mocker.patch.object(screen, "_run_task")

    screen.action_discover_hosts()

    mock_run_task.assert_called_once_with(
        taskname="discover",
        message="Discovering all hosts...",
        no_hosts_message="No hosts available to discover.",
    )


def test_dashboard_on_screen_resume_dirty(mocker):
    """Test DashboardScreen on_screen_resume when screen is dirty."""
    screen = DashboardScreen()

    # Mock screenflags
    mock_screenflags = mocker.patch("exosphere.ui.dashboard.screenflags")
    mock_screenflags.is_screen_dirty.return_value = True

    # Mock refresh_hosts
    mock_refresh = mocker.patch.object(screen, "refresh_hosts")

    screen.on_screen_resume()

    mock_screenflags.is_screen_dirty.assert_called_once_with("dashboard")
    mock_refresh.assert_called_once()
    mock_screenflags.flag_screen_clean.assert_called_once_with("dashboard")


def test_dashboard_on_screen_resume_clean(mocker):
    """Test DashboardScreen on_screen_resume when screen is clean."""
    screen = DashboardScreen()

    # Mock screenflags
    mock_screenflags = mocker.patch("exosphere.ui.dashboard.screenflags")
    mock_screenflags.is_screen_dirty.return_value = False

    # Mock refresh_hosts
    mock_refresh = mocker.patch.object(screen, "refresh_hosts")

    screen.on_screen_resume()

    mock_screenflags.is_screen_dirty.assert_called_once_with("dashboard")
    mock_refresh.assert_not_called()
    mock_screenflags.flag_screen_clean.assert_not_called()


def test_dashboard_run_task_no_inventory(mocker):
    """Test DashboardScreen _run_task method with no inventory."""
    screen = DashboardScreen()

    # Mock context with no inventory
    mocker.patch("exosphere.ui.dashboard.context.inventory", None)

    # Mock app using PropertyMock
    mock_app = mocker.MagicMock()
    mocker.patch.object(
        type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
    )

    screen._run_task("test", "Testing...", "No hosts message")

    mock_app.push_screen.assert_called_once()
    # Verify ErrorScreen is pushed
    args = mock_app.push_screen.call_args[0][0]
    assert "ErrorScreen" in str(type(args))


def test_dashboard_run_task_no_hosts(mocker, mock_context):
    """Test DashboardScreen _run_task method with no hosts."""
    screen = DashboardScreen()
    mock_context.inventory.hosts = []

    # Mock app using PropertyMock
    mock_app = mocker.MagicMock()
    mocker.patch.object(
        type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
    )

    screen._run_task("test", "Testing...", "No hosts message")

    mock_app.push_screen.assert_called_once()
    # Verify ErrorScreen is pushed with no hosts message
    args = mock_app.push_screen.call_args[0][0]
    assert "ErrorScreen" in str(type(args))


def test_dashboard_run_task_with_hosts(mocker, mock_context, host_online):
    """Test DashboardScreen _run_task method with hosts."""
    screen = DashboardScreen()
    mock_context.inventory.hosts = [host_online]

    # Mock app using PropertyMock
    mock_app = mocker.MagicMock()
    mocker.patch.object(
        type(screen), "app", new_callable=mocker.PropertyMock, return_value=mock_app
    )

    # Mock post_message
    mock_post_message = mocker.patch.object(screen, "post_message")

    screen._run_task("ping", "Pinging...", "No hosts message")

    mock_app.push_screen.assert_called_once()
    # Verify ProgressScreen is pushed
    args = mock_app.push_screen.call_args[0][0]
    assert "ProgressScreen" in str(type(args))

    # Test the callback function
    callback = mock_app.push_screen.call_args[1]["callback"]
    callback(None)  # Simulate task completion

    mock_post_message.assert_called_once()
    message = mock_post_message.call_args[0][0]
    assert isinstance(message, HostStatusChanged)
    assert message.current_screen == "dashboard"
