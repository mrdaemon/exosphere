"""
Typer Library Contract Smoketests

Since 0.26.0, Typer has vendored Click and does not expose some of the
internals or Click objects we relied on to cover the gaps in the API.

As a result, most of our code has been either ported to native Typer APIs,
or in the many cases where this isn't possible, duck-typed or anchored off
*assumptions* and (reasonable) expectations around what essentially is more
or less leaking through the public API surface.

Since this is more fragile than I'd like, and since the REPL is very much
the centerpiece of the Exosphere UX, this test suite exists to validate
these assumptions, preferably not against mocks, but against real Typer apps.

Typer has signaled that the embedded Click surface may change in the future,
and so the REPL deliberately duck-types or anchors off public symbols to
potentially survive these changes, and is generally made to be defensive
and to degrade gracefully if these assumptions break.

Should this test suite go belly up on a Typer upgrade, this is a clear
indicator that something went wrong or changed.

The repository is setup to run the test suites (min, pin and latest)
whenever Typer updates, so we will know early.

"""

import enum
from typing import cast

import pytest
import typer
from prompt_toolkit.history import InMemoryHistory
from typer import Context
from typer.core import TyperCommand, TyperGroup
from typer.main import get_command

from exosphere.repl import (
    ExosphereCompleter,
    ExosphereREPL,
    _NoArgsIsHelpError,
    _NoArgsIsHelpUnavailable,
)


class SortField(str, enum.Enum):
    """Stand-in for an Enum-backed option (like the real --sort)"""

    host = "host"
    os = "os"
    flavor = "flavor"
    status = "status"


@pytest.fixture
def sample_app():
    """
    A sample Typer app shaped like Exosphere, more or less

    - Two groups with no_args_is_help=True
    - One leaf with a required arg + bool flag + value option
    - One leaf with an Enum option

    Returns a tuple of (app, recorder) where the app is the Typer app,
    and recorder is a list of callback invocations.
    """
    recorder: list = []

    root = typer.Typer()
    host_app = typer.Typer(no_args_is_help=True)
    inv_app = typer.Typer(no_args_is_help=True)
    root.add_typer(host_app, name="host")
    root.add_typer(inv_app, name="inventory")

    @host_app.command()
    def show(name: str, updates: bool = False, port: int = 22) -> None:
        recorder.append(("show", name, updates, port))

    @inv_app.command()
    def status(sort: SortField = SortField.host) -> None:
        recorder.append(("status", sort))

    return root, recorder


def _make_repl(app, mocker) -> ExosphereREPL:
    """
    Build a REPL bound to a real command tree

    History component is explicitly subbed for InMemoryHistory to avoid
    filesystem I/O in tests, or side effects.
    """
    mocker.patch.object(ExosphereREPL, "_setup_history", return_value=InMemoryHistory())
    ctx = mocker.Mock(spec=Context)
    ctx.command = get_command(app)
    return ExosphereREPL(ctx)


# Narrow get_command() to TyperGroups, avoids having to scatter casts
# everywhere through the tests.
def _root(app) -> TyperGroup:
    return cast(TyperGroup, get_command(app))


def _group(parent: TyperGroup, name: str) -> TyperGroup:
    return cast(TyperGroup, parent.commands[name])


def _leaf(parent: TyperGroup, name: str) -> TyperCommand:
    return cast(TyperCommand, parent.commands[name])


class TestTyperContract:
    def test_noargsishelp_symbol_resolves(self) -> None:
        """
        Ensure NoArgsIsHelpError resolves and lives in the expected Exit module.

        If typer removes or relocates it, the REPL falls back to the
        unraisable sentinel, which we can check for.
        """
        assert _NoArgsIsHelpError is not _NoArgsIsHelpUnavailable
        assert issubclass(_NoArgsIsHelpError, BaseException)
        assert _NoArgsIsHelpError.__name__ == "NoArgsIsHelpError"

    def test_command_node_types_match_real_tree(self, sample_app) -> None:
        """
        Ensure the command node types match the real Typer tree.
        """
        root, _ = sample_app
        root_cmd = _root(root)
        host = _group(root_cmd, "host")
        show = _leaf(host, "show")

        assert isinstance(root_cmd, TyperGroup)
        assert isinstance(host, TyperGroup)
        assert isinstance(show, TyperCommand)
        # Groups are not leaves and vice versa: the union is genuinely needed.
        assert not isinstance(show, TyperGroup)

    def test_enum_option_is_introspectable_as_choice(self, sample_app) -> None:
        """
        Ensure an Enum option is detectable as a choice-like param for tab completion

        (previously handled through click.Choice)
        """
        root, _ = sample_app
        root_cmd = _root(root)
        status = _leaf(_group(root_cmd, "inventory"), "status")
        completer = ExosphereCompleter(root_cmd)

        values = completer._get_choice_option_values(status, "--sort")
        assert values == ["host", "os", "flavor", "status"]

    def test_bool_flag_is_introspectable(self, sample_app) -> None:
        """
        Ensure a bool option is detectable as a flag for tab completion
        """
        root, _ = sample_app
        root_cmd = _root(root)
        show = _leaf(_group(root_cmd, "host"), "show")
        completer = ExosphereCompleter(root_cmd)

        assert completer._is_flag_option(show, "--updates") is True
        assert completer._is_flag_option(show, "--port") is False

    def test_help_raises_typer_exit_and_is_swallowed(
        self, sample_app, mocker, capsys
    ) -> None:
        """
        Ensure invoking --help exits via typer.Exit and is caught by the REPL.

        This is important because otherwise it will get caught by the
        REPL's catch-all and treated as a dirty, filthy, shitty error.
        This is not something you want out of --help as behavior.
        """
        root, _ = sample_app
        repl = _make_repl(root, mocker)

        repl._execute_typer_command(["host", "show", "--help"])
        out = capsys.readouterr().out

        assert "Error executing" not in out
        assert "--help" in out or "Usage" in out

    def test_no_args_group_appends_requires_arguments(
        self, sample_app, mocker, capsys
    ) -> None:
        """
        Ensure invoking a no_args_is_help group with no subcommand behaves

        We would expect typer to print the help for the group AND raise
        NoArgsIsHelpError (which is a Click exception), which is how
        the REPL detects this case and appends the "requires argument"
        message to the user-facing output.

        This test guards against Typer changing this mechanism, regardless
        of *how* -- it doesn't matter. If the "require arguments" line
        stops working, this fails.
        """
        root, _ = sample_app
        repl = _make_repl(root, mocker)

        repl._execute_typer_command(["host"])
        out = capsys.readouterr().out

        assert "requires arguments" in out  # the REPL's message (ours)
        assert "Usage" in out or "show" in out  # Typer did its job

    def test_dispatch_runs_command_callback(self, sample_app, mocker) -> None:
        """
        Ensure ctx.command is the group and dispatches

        We want to ensure that the leaf callback is actually dispatched with
        the parsed args, which is the whole point.
        """
        root, recorder = sample_app
        repl = _make_repl(root, mocker)

        repl._execute_typer_command(["host", "show", "web01", "--updates"])

        assert recorder == [("show", "web01", True, 22)]
