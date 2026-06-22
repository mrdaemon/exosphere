import types

import pytest

from exosphere.commands import utils as utils_module
from exosphere.objects import Host, HostOperation


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


@pytest.fixture
def wide_console(patch_console):
    """Install deterministic, wide consoles for utils' own output."""
    patch_console(utils_module)


def _token(value: str):
    """Build a minimal Cyclopts-like token carrying a value."""
    return types.SimpleNamespace(value=value)


class TestGetInventory:
    """Test the get_inventory function."""

    def test_get_inventory_success(self, mock_context, mock_inventory):
        """Test successful inventory retrieval."""
        mock_context.inventory = mock_inventory

        result = utils_module.get_inventory()

        assert result is mock_inventory

    def test_get_inventory_none_raises_exit(self, mock_context):
        """Test that an uninitialized inventory raises SystemExit (app error)."""
        mock_context.inventory = None

        with pytest.raises(SystemExit) as exc_info:
            utils_module.get_inventory()

        assert exc_info.value.code == 2  # Application error

    def test_get_inventory_none_prints_error(self, mock_context, capsys):
        """Test that None inventory prints error message."""
        mock_context.inventory = None

        with pytest.raises(SystemExit):
            utils_module.get_inventory()

        captured = capsys.readouterr()
        assert "Inventory is not initialized" in captured.err


class TestResolveHost:
    """Test the resolve_host argument converter."""

    def test_resolve_host_success(self, mock_context, mock_inventory, mock_host):
        """A known host name resolves to the Host object."""
        mock_context.inventory = mock_inventory
        mock_inventory.get_host.return_value = mock_host

        result = utils_module.resolve_host(Host, [_token("test-host")])

        assert result is mock_host
        mock_inventory.get_host.assert_called_once_with("test-host")

    def test_resolve_host_not_found_raises(self, mock_context, mock_inventory):
        """An unknown host name raises ValueError (surfaced as an input error)."""
        mock_context.inventory = mock_inventory
        mock_inventory.get_host.return_value = None

        with pytest.raises(ValueError, match="not found in inventory"):
            utils_module.resolve_host(Host, [_token("nonexistent")])

    def test_resolve_host_uninitialized_inventory(self, mock_context):
        """An uninitialized inventory raises ValueError mid-parse."""
        mock_context.inventory = None

        with pytest.raises(ValueError, match="not initialized"):
            utils_module.resolve_host(Host, [_token("test-host")])


class TestRequires:
    """Tests for the requires() group-validator factory."""

    @staticmethod
    def _app():
        from typing import Annotated, Optional

        from cyclopts import App, Group, Parameter

        group = Group(
            "Deps", validator=utils_module.arg_requires_arg("dependent", "required")
        )
        app = App(name="t")

        @app.command
        def run(
            dependent: Annotated[
                bool, Parameter(name=["--dependent"], negative="", group=group)
            ] = False,
            required: Annotated[
                Optional[str], Parameter(name=["--required"], group=group)
            ] = None,
        ) -> int:
            return 0

        return app

    def test_dependent_without_required_errors(self, capsys):
        """The dependent flag without its requirement is an input error."""
        with pytest.raises(SystemExit) as exc_info:
            self._app()(["run", "--dependent"])

        assert exc_info.value.code == 1
        # Message is derived from the arguments' primary CLI names.
        assert "--dependent requires --required" in capsys.readouterr().err

    def test_dependent_with_required_ok(self):
        """Both supplied is valid."""
        code = self._app()(
            ["run", "--dependent", "--required", "x"], result_action="return_value"
        )
        assert code == 0

    def test_neither_ok(self):
        """Neither supplied is valid (the rule only triggers on the dependent)."""
        code = self._app()(["run"], result_action="return_value")
        assert code == 0

    def test_required_alone_ok(self):
        """The required flag alone is valid."""
        code = self._app()(["run", "--required", "x"], result_action="return_value")
        assert code == 0


class TestGetHostsOrAll:
    """Test the get_hosts_or_all helper."""

    def test_all_hosts_when_none_given(self, mock_context, mock_inventory, mocker):
        """An empty selection returns all inventory hosts."""
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"
        mock_inventory.hosts = [host1, host2]
        mock_context.inventory = mock_inventory

        result = utils_module.get_hosts_or_all(())

        assert result == [host1, host2]

    def test_explicit_hosts_returned(self, mock_context, mock_inventory, mocker):
        """Explicitly provided (already-resolved) hosts are returned as-is."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        host2 = mocker.Mock()
        host2.name = "host2"

        result = utils_module.get_hosts_or_all((host1, host2))

        assert result == [host1, host2]

    def test_empty_inventory_returns_none(
        self, mock_context, mock_inventory, wide_console, capsys
    ):
        """An empty inventory yields None with an error message."""
        mock_inventory.hosts = []
        mock_context.inventory = mock_inventory

        result = utils_module.get_hosts_or_all(())

        assert result is None
        assert "No hosts found in inventory" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "supported_count,unsupported_count,expected_count",
        [
            (2, 0, 2),  # All supported
            (2, 1, 2),  # Mix of supported/unsupported (from full inventory)
        ],
        ids=["supported_only", "mixed"],
    )
    def test_supported_only_filters(
        self,
        mock_context,
        mock_inventory,
        mocker,
        supported_count,
        unsupported_count,
        expected_count,
    ):
        """supported_only returns only supported hosts (from the full inventory)."""
        hosts = []
        for i in range(supported_count):
            host = mocker.Mock()
            host.name = f"supported{i + 1}"
            host.supported = True
            host.package_manager = "apt"
            hosts.append(host)
        for i in range(unsupported_count):
            host = mocker.Mock()
            host.name = f"unsupported{i + 1}"
            host.supported = False
            host.package_manager = None
            hosts.append(host)

        mock_inventory.hosts = hosts
        mock_context.inventory = mock_inventory

        # Empty selection -> drawn from inventory; no warning for inventory-wide.
        result = utils_module.get_hosts_or_all((), supported_only=True)

        assert result is not None
        assert len(result) == expected_count

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
    def test_supported_only_none_available(
        self,
        mock_context,
        mock_inventory,
        wide_console,
        capsys,
        mocker,
        has_supported,
        has_package_manager,
    ):
        """supported_only with no valid hosts in the inventory returns None."""
        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = has_supported
        host1.package_manager = "apt" if has_package_manager else None

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        mock_inventory.hosts = [host1, host2]
        mock_context.inventory = mock_inventory

        result = utils_module.get_hosts_or_all((), supported_only=True)

        assert result is None
        assert "No supported hosts found in inventory" in capsys.readouterr().err

    def test_supported_only_explicit_warns(
        self, mock_context, mock_inventory, wide_console, capsys, mocker
    ):
        """supported_only with explicit hosts warns about skipped unsupported ones."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = True
        host1.package_manager = "apt"

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        result = utils_module.get_hosts_or_all((host1, host2), supported_only=True)

        assert result is not None
        assert len(result) == 1
        assert "Unsupported hosts will be skipped" in capsys.readouterr().err

    def test_supported_only_explicit_none_supported(
        self, mock_context, mock_inventory, wide_console, capsys, mocker
    ):
        """supported_only with explicit hosts, none supported, returns None."""
        mock_context.inventory = mock_inventory
        host1 = mocker.Mock()
        host1.name = "host1"
        host1.supported = False
        host1.package_manager = None

        host2 = mocker.Mock()
        host2.name = "host2"
        host2.supported = False
        host2.package_manager = None

        result = utils_module.get_hosts_or_all((host1, host2), supported_only=True)

        assert result is None
        assert "No supported hosts found in specified list" in capsys.readouterr().err


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
            operation=HostOperation.PING,
            task_description="Testing task",
        )

        assert result == []  # No errors
        mock_inventory.run_task.assert_called_once_with(HostOperation.PING, hosts=hosts)
        mock_progress_instance.add_task.assert_called_once_with("Testing task", total=2)
        assert mock_progress_instance.update.call_count == 2

    def test_run_task_displays_skipped_hosts(
        self, mock_inventory, mock_console, mocker
    ):
        """Skipped hosts are displayed separately from total progress"""
        host1 = mocker.Mock()
        host1.name = "host1"
        skipped_host = mocker.Mock()
        skipped_host.name = "irixbox"

        mock_inventory.run_task.return_value = [(host1, None, None)]

        mock_progress = mocker.patch("exosphere.commands.utils.Progress")
        mock_progress_instance = mock_progress.return_value.__enter__.return_value
        mock_progress_instance.add_task.return_value = "task_id"

        result = utils_module.run_task_with_progress(
            inventory=mock_inventory,
            hosts=[host1],
            operation=HostOperation.REFRESH,
            task_description="Refreshing",
            display_hosts=True,
            skipped=[skipped_host],
        )

        assert result == []
        # Only the runnable host is dispatched; total excludes the skipped one.
        mock_inventory.run_task.assert_called_once_with(
            HostOperation.REFRESH, hosts=[host1]
        )
        mock_progress_instance.add_task.assert_called_once_with("Refreshing", total=1)

        # The skipped host is rendered with a SKIPPED status.
        rendered = [
            str(renderable)
            for call in mock_progress_instance.console.print.call_args_list
            for renderable in getattr(call.args[0], "renderables", [])
        ]
        assert any("SKIPPED" in chunk for chunk in rendered)
        assert any("irixbox" in chunk for chunk in rendered)

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
            operation=HostOperation.PING,
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
            operation=HostOperation.PING,
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
            operation=HostOperation.PING,
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
            operation=HostOperation.PING,
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


class TestRequireInteractive:
    """Test the require_interactive decorator."""

    def test_passes_through_when_interactive(self, mocker):
        """Command returns normally when from REPL"""
        mocker.patch.object(utils_module.context, "interactive", True)

        @utils_module.require_interactive
        def cmd(a, b=2):
            return a + b

        assert cmd(1, b=3) == 4

    def test_bails_when_not_interactive(self, mocker, patch_console):
        """Command bails when launched from CLI"""
        patch_console(utils_module)
        mocker.patch.object(utils_module.context, "interactive", False)
        called = mocker.Mock()

        @utils_module.require_interactive
        def cmd():
            called()

        with pytest.raises(SystemExit) as exc_info:
            cmd()

        assert exc_info.value.code == 2
        assert not called.called

    def test_is_signature_transparent(self):
        """
        Ensure the wrapper preserves the original signature
        We do this mostly to ensure we don't break Cyclopts
        """
        import inspect

        def cmd(host, *, verbose: bool = False) -> int:
            return 0

        wrapped = utils_module.require_interactive(cmd)

        assert wrapped.__name__ == "cmd"
        assert inspect.signature(wrapped) == inspect.signature(cmd)
