import pytest

# Import fixtures from Fabric's suite, for general availability in tests.
# We also disable linter warnings for unused imports, since they are used elsewhere.
from fabric.testing.fixtures import connection  # noqa: F401
from rich.console import Console

from exosphere.commands import utils as utils_module
from exosphere.objects import Host


def _make_console(stderr: bool = False) -> Console:
    """
    Build a deterministic Rich console for tests.

    Setups a Rich console object with a wide fixed width, no colors,
    and disabled special handling so tests are uniform across platforms.

    It is generally awful to extract text out of Rich console output
    due to all the ways it autoconfigures itself based on the terminal.
    """
    return Console(
        stderr=stderr,
        force_terminal=True,
        color_system=None,
        highlight=False,
        width=200,
        legacy_windows=False,
    )


@pytest.fixture
def rich_console():
    """
    General fixture for constructing a deterministic Rich console

    Returns a callable that constructs a deterministic Rich Console
    with the same configuration as patch_console.

    Fixed width, no colors, disabled special handling.
    """
    return _make_console


@pytest.fixture
def patch_console(mocker, request):
    """
    Install deterministic Rich consoles onto a CLI module.

    Returns an installer callable that patches the module under test
    and replaces its "console" and "err_console" (which are usually
    shared across all the CLI through commands.utils) with
    deterministic ones.

    This can patch any module, but is intended for CLI ones.

    It also adds finalizers that restore the original consoles after
    a test runs, making it perfectly suitable for fixtures.

    """
    out = _make_console()
    err = _make_console(stderr=True)

    def _install(module) -> None:
        if hasattr(module, "console"):
            mocker.patch.object(module, "console", out)
        if hasattr(module, "err_console"):
            mocker.patch.object(module, "err_console", err)
        mocker.patch.object(utils_module, "console", out)
        mocker.patch.object(utils_module, "err_console", err)

        # Console object are bound to the app. These properties have
        # setters, but no deleters, so mocker.patch.object can't
        # restore them automatically. We set and restore manually here
        # instead.
        app = getattr(module, "app", None)
        if app is not None:
            original_console = app.console
            original_error_console = app.error_console
            app.console = out
            app.error_console = err

            def _restore() -> None:
                app.console = original_console
                app.error_console = original_error_console

            request.addfinalizer(_restore)

    return _install


@pytest.fixture
def make_host(mocker):
    """
    Factory fixture for mock ``Host`` objects.

    Returns a callable that uses autospec to build an instance with the
    canonical attributes of the Host class used throughout the test
    suite.

    The ``updates`` and ``security_updates`` attributes can be set to
    either an int (which will fill it that many mocks) or an explicit
    list of objects.

    Everything else can be kwargs overridden.

    Defaults mock a plain, online, discovered host with no pending
    updates.
    """

    def _make(
        name: str = "test-host",
        *,
        updates: int | list = 0,
        security_updates: int | list = 0,
        **attrs,
    ) -> Host:
        host = mocker.create_autospec(Host, instance=True)
        host.name = name
        host.updates = (
            list(updates)
            if isinstance(updates, list)
            else [mocker.Mock() for _ in range(updates)]
        )
        host.security_updates = (
            list(security_updates)
            if isinstance(security_updates, list)
            else [mocker.Mock() for _ in range(security_updates)]
        )

        defaults = {
            "os": "linux",
            "flavor": None,
            "version": None,
            "online": True,
            "supported": True,
            "is_stale": False,
            "description": None,
            "needs_reboot": None,
        }
        for key, value in {**defaults, **attrs}.items():
            setattr(host, key, value)

        return host

    return _make


@pytest.fixture
def wire_get_host():
    """
    Mock inventory wiring fixture, for get_host resolution by name.

    Essentially mocks just enough of the get_host method, in a way
    that mirrors the real HostArg converter path, so commands and
    screens invoked with explicit host names find their target.
    """

    def _wire(inventory):
        inventory.get_host.side_effect = lambda name: next(
            (h for h in inventory.hosts if h.name == name), None
        )
        return inventory

    return _wire
