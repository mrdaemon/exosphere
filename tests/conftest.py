import pytest

# Import fixtures from Fabric's suite, for general availability in tests.
# We also disable linter warnings for unused imports, since they are used elsewhere.
from fabric.testing.fixtures import connection  # noqa: F401
from rich.console import Console

from exosphere.commands import utils as utils_module


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
