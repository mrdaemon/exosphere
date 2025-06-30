import pytest

from exosphere.objects import Host
from exosphere.ui.dashboard import DashboardScreen, HostWidget


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


def test_hostwidget_make_contents_online(host_online):
    """Test that HostWidget generates correct contents for an online host."""
    widget = HostWidget(host_online)
    contents = widget.make_contents()
    assert "[green]Online[/green]" in contents
    assert "Ubuntu 22.04" in contents
    assert "Test host" in contents


def test_hostwidget_make_contents_offline_undiscovered():
    """Test that HostWidget generates correct contents for an undiscovered host."""
    host = Host(name="host3", ip="127.0.0.4", description=None)
    host.online = False
    host.flavor = None
    host.version = None
    widget = HostWidget(host)
    contents = widget.make_contents()
    assert "[red]Offline[/red]" in contents
    assert "(Undiscovered)" in contents


def test_dashboard_on_mount_sets_titles():
    """Test that DashboardScreen sets the correct titles on mount."""
    screen = DashboardScreen()
    screen.on_mount()
    assert screen.title == "Exosphere"
    assert screen.sub_title == "Dashboard"


def test_dashboard_action_ping_all_hosts_calls_run_task(mocker):
    """Test that action_ping_all_hosts calls _run_task with correct parameters."""
    screen = DashboardScreen()
    mock = mocker.patch.object(screen, "_run_task")
    screen.action_ping_all_hosts()
    mock.assert_called_with(
        taskname="ping",
        message="Pinging all hosts...",
        no_hosts_message="No hosts available to ping.",
    )


def test_dashboard_action_discover_hosts_calls_run_task(mocker):
    """Test that action_discover_hosts calls _run_task with correct parameters."""
    screen = DashboardScreen()
    mock = mocker.patch.object(screen, "_run_task")
    screen.action_discover_hosts()
    mock.assert_called_with(
        taskname="discover",
        message="Discovering all hosts...",
        no_hosts_message="No hosts available to discover.",
    )
