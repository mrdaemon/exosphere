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


def test_hostwidget_make_contents_online(host_online):
    """Test that HostWidget generates correct contents for an online host."""
    widget = HostWidget(host_online)
    contents = widget.make_contents()
    assert "[green]Online[/green]" in contents
    assert "Ubuntu 22.04" in contents
    assert "Test host" in contents
    assert "[b]host1[/b]" in contents


def test_hostwidget_make_contents_offline(host_offline):
    """Test that HostWidget generates correct contents for an offline host."""
    widget = HostWidget(host_offline)
    contents = widget.make_contents()
    assert "[red]Offline[/red]" in contents
    assert "Debian 11" in contents
    assert "(Undiscovered)" not in contents
    assert "\n\n" in contents  # Check for empty description handling
    assert "[b]host2[/b]" in contents


def test_hostwidget_make_contents_offline_undiscovered(host_undiscovered):
    """Test that HostWidget generates correct contents for an undiscovered host."""
    widget = HostWidget(host_undiscovered)
    contents = widget.make_contents()
    assert "[red]Offline[/red]" in contents
    assert "(Undiscovered)" in contents
    assert "[b]host3[/b]" in contents


def test_hostwidget_init():
    """Test HostWidget initialization."""
    host = Host(name="test", ip="127.0.0.1")
    widget = HostWidget(host, id="test-widget")
    assert widget.host == host
    assert widget.id == "test-widget"


def test_hostwidget_refresh_state(mocker, host_online):
    """Test HostWidget refresh_state method."""
    widget = HostWidget(host_online)

    # Mock the query_one method and Label
    mock_label = mocker.MagicMock()
    mock_query_one = mocker.patch.object(widget, "query_one", return_value=mock_label)

    # Initially online
    widget.refresh_state()

    mock_query_one.assert_called_once()
    mock_label.update.assert_called_once()
    mock_label.add_class.assert_called_with("online")
    mock_label.remove_class.assert_called_with("offline")

    # Test with offline host
    mock_label.reset_mock()
    mock_query_one.reset_mock()

    widget.host.online = False
    widget.refresh_state()

    mock_label.add_class.assert_called_with("offline")
    mock_label.remove_class.assert_called_with("online")


def test_hostwidget_compose(mocker, host_online):
    """Test HostWidget compose method."""
    widget = HostWidget(host_online)

    result = list(widget.compose())

    assert len(result) == 1
    # The result should be a Label with correct classes
    label = result[0]
    assert hasattr(label, "classes")


def test_dashboard_on_mount_sets_titles():
    """Test that DashboardScreen sets the correct titles on mount."""
    screen = DashboardScreen()
    screen.on_mount()
    assert screen.title == "Exosphere"
    assert screen.sub_title == "Dashboard"


def test_dashboard_compose_with_hosts(mock_context, host_online, host_offline):
    """Test DashboardScreen compose method with hosts."""
    mock_context.inventory.hosts = [host_online, host_offline]

    screen = DashboardScreen()
    result = list(screen.compose())

    # Should yield Header, HostWidgets for each host, and Footer
    assert len(result) >= 4  # Header + 2 HostWidgets + Footer


def test_dashboard_compose_no_hosts(mock_context):
    """Test DashboardScreen compose method with no hosts."""
    mock_context.inventory.hosts = []

    screen = DashboardScreen()
    result = list(screen.compose())

    # Should yield Header, empty message Label, and Footer
    assert len(result) == 3


def test_dashboard_compose_no_inventory(mocker):
    """Test DashboardScreen compose method with no inventory."""
    mocker.patch("exosphere.ui.dashboard.context.inventory", None)

    screen = DashboardScreen()
    result = list(screen.compose())

    # Should yield Header, empty message Label, and Footer
    assert len(result) == 3


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
