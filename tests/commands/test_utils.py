import pytest
import typer
from rich.panel import Panel

from exosphere.commands import utils as utils_module
from exosphere.objects import Host


@pytest.fixture
def mock_context(mocker):
    """Mock the context module to control inventory state."""
    return mocker.patch.object(utils_module, "context")


@pytest.fixture
def mock_inventory(mocker):
    """Create a mock inventory instance."""
    inventory = mocker.create_autospec(utils_module.Inventory, instance=True)
    inventory.hosts = []
    return inventory


@pytest.fixture
def mock_host(mocker):
    """Create a mock host instance."""
    host = mocker.create_autospec(Host, instance=True)
    host.name = "test-host"
    host.ip = "192.168.1.100"
    host.port = 22
    host.online = True
    return host


@pytest.fixture
def mock_console(mocker):
    """Mock the console objects to capture output."""
    console_mock = mocker.patch.object(utils_module, "console")
    err_console_mock = mocker.patch.object(utils_module, "err_console")
    return console_mock, err_console_mock


class TestGetInventory:
    """Test the get_inventory function."""

    def test_get_inventory_success(self, mock_context, mock_inventory):
        """Test successful inventory retrieval."""
        mock_context.inventory = mock_inventory

        result = utils_module.get_inventory()

        assert result is mock_inventory

    def test_get_inventory_none_raises_exit(self, mock_context):
        """Test that None inventory raises typer.Exit."""
        mock_context.inventory = None

        with pytest.raises(typer.Exit) as exc_info:
            utils_module.get_inventory()

        assert exc_info.value.exit_code == 1

    def test_get_inventory_none_prints_error(self, mock_context, capsys):
        """Test that None inventory prints error message."""
        mock_context.inventory = None

        with pytest.raises(typer.Exit):
            utils_module.get_inventory()

        captured = capsys.readouterr()
        assert "Inventory is not initialized" in captured.err


class TestGetHostOrError:
    """Test the get_host_or_error function."""

    def test_get_host_success(
        self, mock_context, mock_inventory, mock_host, mock_console
    ):
        """Test successful host retrieval."""
        mock_context.inventory = mock_inventory
        mock_inventory.get_host.return_value = mock_host
        console_mock, err_console_mock = mock_console

        result = utils_module.get_host_or_error("test-host")

        assert result is mock_host
        mock_inventory.get_host.assert_called_once_with("test-host")
        err_console_mock.print.assert_not_called()

    def test_get_host_not_found(self, mock_context, mock_inventory, mock_console):
        """Test host not found scenario."""
        mock_context.inventory = mock_inventory
        mock_inventory.get_host.return_value = None
        console_mock, err_console_mock = mock_console

        result = utils_module.get_host_or_error("nonexistent-host")

        assert result is None
        mock_inventory.get_host.assert_called_once_with("nonexistent-host")
        err_console_mock.print.assert_called_once()

        # Check that error panel was created with correct message
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "Host 'nonexistent-host' not found in inventory" in str(
            call_args.renderable
        )

    def test_get_host_inventory_none(self, mock_context):
        """Test behavior when inventory is None."""
        mock_context.inventory = None

        with pytest.raises(typer.Exit):
            utils_module.get_host_or_error("test-host")


class TestGetHostsOrError:
    """Test the get_hosts_or_error function."""

    def test_get_hosts_with_names_success(
        self, mock_context, mock_inventory, mock_console, mocker
    ):
        """Test successful retrieval of specific hosts."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"
        mock_inventory.hosts = [host1, host2]
        console_mock, err_console_mock = mock_console

        result = utils_module.get_hosts_or_error(["host1", "host2"])

        assert result == [host1, host2]
        err_console_mock.print.assert_not_called()

    def test_get_hosts_with_names_partial_match(
        self, mock_context, mock_inventory, mock_console, mocker
    ):
        """Test partial match scenario with some hosts not found."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        mock_inventory.hosts = [host1]
        console_mock, err_console_mock = mock_console

        result = utils_module.get_hosts_or_error(["host1", "nonexistent"])

        assert result is None
        err_console_mock.print.assert_called_once()

        # Check error message contains unmatched hosts
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "nonexistent" in str(call_args.renderable)

    def test_get_hosts_all_hosts_success(
        self, mock_context, mock_inventory, mock_console, mocker
    ):
        """Test retrieval of all hosts when no names specified."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"
        mock_inventory.hosts = [host1, host2]
        console_mock, err_console_mock = mock_console

        result = utils_module.get_hosts_or_error(None)

        assert result == [host1, host2]
        err_console_mock.print.assert_not_called()

    def test_get_hosts_all_hosts_empty(
        self, mock_context, mock_inventory, mock_console
    ):
        """Test behavior when inventory has no hosts."""
        mock_context.inventory = mock_inventory
        mock_inventory.hosts = []
        console_mock, err_console_mock = mock_console

        result = utils_module.get_hosts_or_error(None)

        assert result is None
        err_console_mock.print.assert_called_once()

        # Check error message
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "No hosts found in inventory" in str(call_args.renderable)

    def test_get_hosts_inventory_none(self, mock_context):
        """Test behavior when inventory is None."""
        mock_context.inventory = None

        with pytest.raises(typer.Exit):
            utils_module.get_hosts_or_error(["host1"])

    @pytest.mark.parametrize(
        "supported_hosts_count,unsupported_hosts_count,expected_count",
        [
            (2, 0, 2),  # All supported
            (2, 1, 2),  # Mix of supported/unsupported
        ],
        ids=["supported only", "mixed"],
    )
    def test_get_hosts_supported_only_success(
        self,
        mock_context,
        mock_inventory,
        mock_console,
        mocker,
        supported_hosts_count,
        unsupported_hosts_count,
        expected_count,
    ):
        """Test that supported_only returns only supported hosts."""
        mock_context.inventory = mock_inventory
        console_mock, err_console_mock = mock_console

        # Generate crappy host mocks
        hosts = []
        for i in range(supported_hosts_count):
            host = mocker.Mock()
            host.name = f"supported{i + 1}"
            host.supported = True
            host.package_manager = "apt"
            hosts.append(host)

        for i in range(unsupported_hosts_count):
            host = mocker.Mock()
            host.name = f"unsupported{i + 1}"
            host.supported = False
            host.package_manager = None
            hosts.append(host)

        mock_inventory.hosts = hosts

        result = utils_module.get_hosts_or_error(supported_only=True)

        assert result is not None
        assert len(result) == expected_count
        err_console_mock.print.assert_not_called()

    @pytest.mark.parametrize(
        "has_supported,has_package_manager",
        [
            (False, False),  # Not supported, no package manager
            (True, False),  # Supported but no package manager
            (False, True),  # Not supported but has package manager (?!)
        ],
        ids=[
            "unsupported",
            "supported+undiscovered",
            "unsupported+pkgmgr",
        ],
    )
    def test_get_hosts_supported_only_none_available(
        self,
        mock_context,
        mock_inventory,
        mock_console,
        mocker,
        has_supported,
        has_package_manager,
    ):
        """Test supported_only with no valid supported hosts."""
        mock_context.inventory = mock_inventory
        console_mock, err_console_mock = mock_console

        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = has_supported
        host1.package_manager = "apt" if has_package_manager else None

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        mock_inventory.hosts = [host1, host2]

        result = utils_module.get_hosts_or_error(supported_only=True)

        assert result is None
        err_console_mock.print.assert_called_once()
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "No supported hosts found in inventory" in str(call_args.renderable)

    def test_get_hosts_supported_only_with_names_warning(
        self, mock_context, mock_inventory, mock_console, mocker
    ):
        """Test supported_only with specific names shows warning for unsupported."""
        mock_context.inventory = mock_inventory
        console_mock, err_console_mock = mock_console

        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = True
        host1.package_manager = "apt"

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        mock_inventory.hosts = [host1, host2]

        result = utils_module.get_hosts_or_error(
            names=["host1", "host2"], supported_only=True
        )

        assert result is not None
        assert len(result) == 1
        err_console_mock.print.assert_called_once()
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "Unsupported hosts will be skipped" in str(call_args.renderable)

    def test_get_hosts_supported_only_with_names_none_supported(
        self, mock_context, mock_inventory, mock_console, mocker
    ):
        """Test supported_only with specific names when none are supported."""
        mock_context.inventory = mock_inventory
        console_mock, err_console_mock = mock_console

        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = False
        host1.package_manager = None

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        mock_inventory.hosts = [host1, host2]

        result = utils_module.get_hosts_or_error(
            names=["host1", "host2"], supported_only=True
        )

        assert result is None
        err_console_mock.print.assert_called_once()
        call_args = err_console_mock.print.call_args[0][0]
        assert isinstance(call_args, Panel)
        assert "No supported hosts found in specified list" in str(call_args.renderable)


class TestRunTaskWithProgress:
    """Test the run_task_with_progress function."""

    def test_run_task_success_no_errors(self, mock_inventory, mock_console, mocker):
        """Test successful task execution with no errors."""
        console_mock, err_console_mock = mock_console

        # Mock hosts
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"
        hosts = [host1, host2]

        # Mock inventory.run_task to return successful results
        mock_inventory.run_task.return_value = [
            (host1, None, None),  # success
            (host2, None, None),  # success
        ]

        # Mock Progress context manager
        mock_progress = mocker.patch("exosphere.commands.utils.Progress")
        mock_progress_instance = mock_progress.return_value.__enter__.return_value
        mock_progress_instance.add_task.return_value = "task_id"

        result = utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=hosts,
            task_name="test_task",
            task_description="Testing task",
        )

        assert result == []  # No errors
        mock_inventory.run_task.assert_called_once_with("test_task", hosts=hosts)
        mock_progress_instance.add_task.assert_called_once_with("Testing task", total=2)
        assert mock_progress_instance.update.call_count == 2

    def test_run_task_with_errors(self, mock_inventory, mock_console, mocker):
        """Test task execution with some errors."""
        console_mock, err_console_mock = mock_console

        # Mock hosts
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"
        hosts = [host1, host2]

        # Mock inventory.run_task to return mixed results
        error = Exception("Test error")
        mock_inventory.run_task.return_value = [
            (host1, None, None),  # success
            (host2, None, error),  # failure
        ]

        # Mock Progress context manager
        mock_progress = mocker.patch("exosphere.commands.utils.Progress")
        mock_progress_instance = mock_progress.return_value.__enter__.return_value
        mock_progress_instance.add_task.return_value = "task_id"

        result = utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=hosts,
            task_name="test_task",
            task_description="Testing task",
        )

        assert result == [("host2", error)]
        assert (
            mock_progress_instance.console.print.call_count == 2
        )  # Two status displays

    def test_run_task_immediate_error_display(
        self, mock_inventory, mock_console, mocker
    ):
        """Test immediate error display option."""
        console_mock, err_console_mock = mock_console

        # Mock hosts
        host1 = mocker.Mock()
        host1.name = "host1"
        hosts = [host1]

        # Mock inventory.run_task to return error
        error = Exception("Test error")
        mock_inventory.run_task.return_value = [
            (host1, None, error),
        ]

        # Mock Progress context manager
        mock_progress = mocker.patch("exosphere.commands.utils.Progress")
        mock_progress_instance = mock_progress.return_value.__enter__.return_value
        mock_progress_instance.add_task.return_value = "task_id"

        utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=hosts,
            task_name="test_task",
            task_description="Testing task",
            immediate_error_display=True,
        )

        # Check that immediate error was displayed
        assert (
            mock_progress_instance.console.print.call_count == 2
        )  # Error + status display

    def test_run_task_no_host_display(self, mock_inventory, mock_console, mocker):
        """Test with display_hosts=False."""
        console_mock, err_console_mock = mock_console

        # Mock hosts
        host1 = mocker.Mock()
        host1.name = "host1"
        hosts = [host1]

        # Mock inventory.run_task to return success
        mock_inventory.run_task.return_value = [
            (host1, None, None),
        ]

        # Mock Progress context manager
        mock_progress = mocker.patch("exosphere.commands.utils.Progress")
        mock_progress_instance = mock_progress.return_value.__enter__.return_value
        mock_progress_instance.add_task.return_value = "task_id"

        utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=hosts,
            task_name="test_task",
            task_description="Testing task",
            display_hosts=False,
        )

        # Should not display host status
        mock_progress_instance.console.print.assert_not_called()

    def test_run_task_custom_progress_args(self, mock_inventory, mock_console, mocker):
        """Test with custom progress arguments."""
        console_mock, err_console_mock = mock_console

        # Mock hosts
        host1 = mocker.Mock()
        host1.name = "host1"
        hosts = [host1]

        mock_inventory.run_task.return_value = [(host1, None, None)]

        # Mock Progress context manager
        mock_progress = mocker.patch("exosphere.commands.utils.Progress")

        custom_args = ("arg1", "arg2")
        utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=hosts,
            task_name="test_task",
            task_description="Testing task",
            progress_args=custom_args,
        )

        # Check that custom args were passed to Progress
        mock_progress.assert_called_once_with(transient=True, *custom_args)


class TestStatusFormats:
    """Test the STATUS_FORMATS constant."""

    def test_status_formats_structure(self):
        """Test that STATUS_FORMATS has expected structure."""
        assert "success" in utils_module.STATUS_FORMATS
        assert "failure" in utils_module.STATUS_FORMATS

        # Check that values are rich markup strings
        assert "[bold green]" in utils_module.STATUS_FORMATS["success"]
        assert "[bold red]" in utils_module.STATUS_FORMATS["failure"]


class TestConsoleObjects:
    """Test the console objects."""

    def test_console_objects_exist(self):
        """Test that console objects are properly initialized."""
        assert hasattr(utils_module, "console")
        assert hasattr(utils_module, "err_console")

        # Should be Console instances
        from rich.console import Console

        assert isinstance(utils_module.console, Console)
        assert isinstance(utils_module.err_console, Console)
