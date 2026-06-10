"""
Tests for the Exosphere REPL (Cyclopts-based).

A small Cyclopts app shaped like Exosphere (groups, a leaf with a
positional, host + flags, a variadic-host leaf, an enum option,
and a couple of leaves that raise) stands in for the real command tree.
"""

import enum
import logging
from typing import Annotated

import pytest
from cyclopts import App, Parameter
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory, InMemoryHistory

from exosphere import context as app_context
from exosphere.commands.utils import HOST_PARAMETER, HostArg
from exosphere.objects import Host
from exosphere.repl import ExosphereCompleter, ExosphereREPL

HOST_NAMES = ["web01", "web02", "db01"]


class SortField(str, enum.Enum):
    """Cheap stand-in enum for a Choice option."""

    host = "host"
    os = "os"
    flavor = "flavor"
    status = "status"


@pytest.fixture
def fake_exosphere(rich_console):
    """
    A sample App shaped vaguely like Exosphere for testing the REPL.

    - Three visible groups (host, inventory, sudo) and one hidden group
      (connections)
    - host.show: positional host + bool flag + int value option
    - host.ping: variadic host
    - inventory.status: enum option
    - inventory.boom / inventory.explode: raise to exercise error
      handling through commands
    - sudo.generate: host-typed *option* (--host)
    - connections.close: variadic host (hidden group)

    Every app is bound to color-free consoles so framework output (help
    and error panels) is deterministic.

    Returns (root, recorder) where "recorder" collects leaf invocations.
    """
    recorder: list = []
    out, err = rich_console(), rich_console(stderr=True)

    def _app(name, help_text="", show=True):
        return App(
            name=name,
            help=help_text,
            help_flags=["--help"],
            version_flags=[],
            show=show,
            console=out,
            error_console=err,
        )

    root = _app("exosphere")
    host_app = _app("host", "Host management commands")
    inv_app = _app("inventory", "Inventory commands")
    sudo_app = _app("sudo", "Sudo policy commands")
    conn_app = _app("connections", "Connection commands", show=False)

    # Setup subcommand structure
    root.command(host_app)
    root.command(inv_app)
    root.command(sudo_app)
    root.command(conn_app)

    # Crappy stand in implementations
    @host_app.command
    def show(host: HostArg, /, *, updates: bool = False, port: int = 22) -> None:
        recorder.append(("show", host, updates, port))

    @host_app.command
    def ping(*names: HostArg) -> None:
        recorder.append(("ping", names))

    @inv_app.command
    def status(*, sort: SortField = SortField.host) -> None:
        recorder.append(("status", sort))

    @inv_app.command
    def boom() -> None:
        raise SystemExit(2)

    @inv_app.command
    def explode() -> None:
        raise RuntimeError("Out of entropy, next shipment in 3 days")

    @sudo_app.command
    def generate(
        *,
        host: Annotated[
            Host | None, HOST_PARAMETER, Parameter(name=["--host", "-h"])
        ] = None,
    ) -> None:
        recorder.append(("generate", host))

    @conn_app.command
    def close(*names: HostArg) -> None:
        recorder.append(("close", names))

    return root, recorder


@pytest.fixture
def completer(fake_exosphere):
    """A completer bound to the sample app with a fixed host list."""
    root, _ = fake_exosphere
    return ExosphereCompleter(root, lambda: list(HOST_NAMES))


@pytest.fixture
def repl(fake_exosphere, mocker, rich_console):
    """
    An instance of the Exosphere REPL bound to the sample app.

    History is subbed out to in-memory to avoid filesystem I/O, and the
    console is made deterministic for output assertions.

    Returns (instance, recorder) where recorder collects leaf invocations.
    """
    root, recorder = fake_exosphere
    mocker.patch.object(ExosphereREPL, "_setup_history", return_value=InMemoryHistory())
    instance = ExosphereREPL(root)
    instance.console = rich_console()
    return instance, recorder


def _raw_completions(completer, text: str) -> list:
    """Return the raw Completion objects for the given input."""
    document = Document(text, cursor_position=len(text))
    return list(completer.get_completions(document, None))


def _completions(completer, text: str) -> list[str]:
    """Return sorted completion texts (trailing space stripped) for input."""
    return sorted(c.text.strip() for c in _raw_completions(completer, text))


class TestReplInit:
    """REPL initialization and setup test suite"""

    def test_history_uses_configured_file(self, fake_exosphere, mocker, tmp_path):
        """History should be setup with file from config"""
        root, _ = fake_exosphere
        history_file = tmp_path / "history.txt"

        mocker.patch(
            "exosphere.repl.app_config",
            {"options": {"history_file": str(history_file)}},
        )

        instance = ExosphereREPL(root)

        assert isinstance(instance.history, FileHistory)

    def test_history_falls_back_to_memory(self, fake_exosphere, mocker, caplog):
        root, _ = fake_exosphere

        # Ensure history file is configured
        mocker.patch(
            "exosphere.repl.app_config",
            {"options": {"history_file": "/some/path"}},
        )

        # Oh no! FileHistory died somehow!
        mocker.patch(
            "exosphere.repl.FileHistory",
            side_effect=OSError("Disk write super died or whatever"),
        )

        caplog.set_level(logging.WARNING, logger="exosphere.repl")

        instance = ExosphereREPL(root)

        assert isinstance(instance.history, InMemoryHistory)
        assert "falling back to in-memory history" in caplog.text

    def test_host_completion_reflects_inventory(self, fake_exosphere, mocker):
        root, _ = fake_exosphere

        mocker.patch.object(
            ExosphereREPL, "_setup_history", return_value=InMemoryHistory()
        )

        fake_inventory = mocker.Mock()
        host1, host2 = mocker.Mock(), mocker.Mock()
        host1.name, host2.name = "alpha", "bravo"
        fake_inventory.hosts = [host1, host2]

        mocker.patch.object(app_context, "inventory", fake_inventory)

        instance = ExosphereREPL(root)

        result = _completions(instance.completer, "host show ")

        assert "alpha" in result
        assert "bravo" in result

    def test_no_inventory_yields_no_host_completion(self, fake_exosphere, mocker):
        root, _ = fake_exosphere

        mocker.patch.object(
            ExosphereREPL, "_setup_history", return_value=InMemoryHistory()
        )
        mocker.patch.object(app_context, "inventory", None)

        instance = ExosphereREPL(root)

        assert _completions(instance.completer, "host show ") == []


class TestCompleterContent:
    """Test suite for the Completer content, specifically"""

    def test_top_level_commands_and_builtins(self, completer):
        result = _completions(completer, "")

        assert "host" in result
        assert "inventory" in result
        assert "exit" in result
        assert "quit" in result
        assert "clear" in result

    def test_prefix_filters_commands(self, completer):
        assert _completions(completer, "inv") == ["inventory"]

    def test_help_completes_command_names(self, completer):
        result = _completions(completer, "help ")

        assert "host" in result
        assert "inventory" in result

    @pytest.mark.parametrize("builtin", ["exit", "quit", "clear"])
    def test_builtins_take_no_arguments(self, completer, builtin):
        """Built-in commands should not offer any completions"""
        assert _completions(completer, f"{builtin} ") == []

    def test_group_subcommands(self, completer):
        result = _completions(completer, "host ")

        assert "show" in result
        assert "ping" in result

    def test_options_only_after_dash(self, completer):
        # Without a dash, no options are offered (only host positionals)
        assert "--updates" not in _completions(completer, "host show ")

        # With a dash, options are offered
        with_dash = _completions(completer, "host show -")
        assert "--updates" in with_dash
        assert "--port" in with_dash
        assert "--help" in with_dash

    def test_only_long_options_are_completed(self, completer):
        result = _completions(completer, "sudo generate -")

        assert "--host" in result
        assert "-h" not in result

        # "-" and "--" should yield the exact same: long options
        assert result == _completions(completer, "sudo generate --")

    def test_enum_option_values(self, completer):
        """Enum options should offer their values"""
        result = _completions(completer, "inventory status --sort ")

        # We use our SortField stand-in here
        # See the local class in this file
        assert SortField.host in result
        assert SortField.os in result
        assert SortField.flavor in result
        assert SortField.status in result

    def test_positional_host_completion(self, completer):
        result = _completions(completer, "host show ")

        assert "web01" in result
        assert "web02" in result
        assert "db01" in result

    def test_host_completion_excludes_used_hosts(self, completer):
        result = _completions(completer, "host ping web01 ")

        assert "web01" not in result
        assert "web02" in result
        assert "db01" in result

    def test_host_option_value_completion(self, completer):
        """The value of a host-typed option completes to host names."""
        result = _completions(completer, "sudo generate --host ")

        assert "web01" in result
        assert "web02" in result
        assert "db01" in result

    def test_non_flag_option_value_offers_nothing(self, completer):
        """Options that aren't flags should not offer completions."""
        assert _completions(completer, "host show --port ") == []

    def test_host_completion_continues_after_a_bool_flag(self, completer):
        """
        A bool flag consumes no value, so completion falls through to the
        command's positional host argument.
        """
        result = _completions(completer, "host show --updates ")

        assert "web01" in result
        assert "web02" in result
        assert "db01" in result

    def test_unknown_command_offers_nothing(self, completer):
        """Unknown commands should not yield completions"""
        assert _completions(completer, "bogus ") == []


class TestCompleterBehavior:
    """Test the readline-like behavior of the completer"""

    def test_unique_match_appends_trailing_space(self, completer):
        """A unique match should have a trailing space for tab completion"""
        raw = _raw_completions(completer, "inv")

        assert len(raw) == 1
        assert raw[0].text == "inventory "

    def test_ambiguous_match_has_no_trailing_space(self, completer):
        """Multiple candidates must not append a space"""
        raw = _raw_completions(completer, "")

        assert len(raw) > 1
        assert all(not c.text.endswith(" ") for c in raw)

    def test_completion_replaces_only_typed_prefix(self, completer):
        """Replace typed prefix, not whole line"""
        raw = _raw_completions(completer, "inv")

        assert raw[0].start_position == -len("inv")

    def test_used_option_is_not_offered_again(self, completer):
        """An option already present on the line is not offered a second time."""
        result = _completions(completer, "host show --updates -")

        assert "--updates" not in result
        assert "--port" in result


class TestReplCommands:
    """REPL behavior during execution of commands"""

    @pytest.mark.parametrize("command", ["exit", "quit"])
    def test_exit_commands_leave_the_loop(self, repl, command):
        """exit and quit should signal the REPL to stop looping."""
        instance, _ = repl

        # exit/quit signal the loop to stop by raising EOFError.
        with pytest.raises(EOFError):
            instance.execute_command(command)

    def test_clear_clears_the_console(self, repl, mocker):
        instance, _ = repl
        mock_clear = mocker.patch.object(instance.console, "clear")

        instance.execute_command("clear")

        mock_clear.assert_called_once()

    def test_parse_error_is_reported(self, repl, capsys):
        instance, _ = repl

        # Unterminated quotes will make shlex raise.
        # We expect this to be displayed, not crash the REPL
        instance.execute_command('host show "unterminated')

        assert "Error parsing command" in capsys.readouterr().out

    def test_known_command_is_dispatched(self, repl):
        instance, recorder = repl

        instance.execute_command("inventory status")

        assert ("status", SortField.host) in recorder

    def test_help_lists_commands_including_hidden_groups(self, repl, capsys):
        instance, _ = repl

        instance.execute_command("help")
        out = capsys.readouterr().out

        assert "host" in out
        assert "inventory" in out
        assert "connections" in out  # hidden group

    def test_command_help_flag_shows_usage(self, repl, capsys):
        instance, _ = repl

        instance.execute_command("host show --help")

        out = capsys.readouterr().out

        assert "show" in out
        assert "--updates" in out

    def test_bare_group_shows_its_subcommands(self, repl, capsys):
        instance, _ = repl

        instance.execute_command("host")
        out = capsys.readouterr().out

        assert "show" in out
        assert "ping" in out

    def test_help_for_builtin_shows_its_description(self, repl, capsys):
        """Builtins describe themselves rather than a CLI command."""
        instance, _ = repl

        instance.execute_command("help exit")
        out = capsys.readouterr().out

        assert "Built-in" in out
        assert instance.builtins["exit"] in out

    def test_help_help_easter_egg(self, repl, capsys):
        """help help does not recurse"""
        instance, _ = repl

        instance.execute_command("help help")

        assert "that is indeed how that works" in capsys.readouterr().out

    def test_help_for_command_is_scoped_to_the_command(self, repl, capsys):
        """help for subcommands route to scoped help."""
        instance, _ = repl

        instance.execute_command("help host")
        out = capsys.readouterr().out

        assert "show" in out  # it is the host group's help
        assert "exosphere" not in out  # root command is stripped

    def test_help_for_unknown_command_falls_back_to_root(self, repl, capsys):
        """Unknown commands show help for root command"""
        instance, _ = repl

        instance.execute_command("help defenestrate")
        out = capsys.readouterr().out

        assert "host" in out
        assert "inventory" in out

    def test_empty_line_is_noop(self, repl, capsys):
        """A blank line dispatches nothing and prints nothing."""
        instance, recorder = repl

        instance.execute_command("   ")

        assert recorder == []
        assert capsys.readouterr().out == ""

    def test_command_exit_code_does_not_leave_the_repl(self, repl):
        """SystemExit must not raise out of the REPL loop"""
        instance, _ = repl

        instance.execute_command("inventory boom")

    def test_unexpected_exception_is_reported(self, repl, capsys):
        """Unexpected exceptions must not raise out of the REPL loop"""
        instance, _ = repl

        # This command in fake_exosphere raises a RuntimeError
        instance.execute_command("inventory explode")

        assert "Error executing" in capsys.readouterr().out

    def test_internal_error_in_builtin_is_reported(self, repl, mocker, capsys):
        """
        The execute_command catch-all reports unexpected failures in the
        built-in handling paths (here, clearing the screen) rather than
        letting them escape the REPL.
        """
        instance, _ = repl
        mocker.patch.object(
            instance.console, "clear", side_effect=RuntimeError("SOMEHOW that failed")
        )

        instance.execute_command("clear")

        assert "Error executing command" in capsys.readouterr().out

    def test_unknown_command_suggests_alternatives(self, repl, capsys):
        """
        Unknown commands should yield a helpful message and suggestions.

        This is built-in Cyclopts functionality, but we want to ensure
        it's correctly wired up through the REPL and not swallowed by
        our own error handling.
        """
        instance, _ = repl

        instance.execute_command("hsot")

        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "Did you mean" in output
        assert "host" in output


class TestReplLoop:
    """Test the interactive loop UX"""

    def test_intro_is_printed(self, repl, mocker, capsys):
        instance, _ = repl
        mocker.patch("exosphere.repl.prompt", side_effect=EOFError)

        instance.cmdloop(intro="Sup, nerds?")

        assert "Sup, nerds?" in capsys.readouterr().out

    def test_blank_input_is_skipped(self, repl, mocker):
        instance, _ = repl
        mocker.patch("exosphere.repl.prompt", side_effect=["   ", EOFError])
        spy = mocker.patch.object(instance, "execute_command")

        instance.cmdloop()

        spy.assert_not_called()

    def test_loop_dispatches_typed_commands(self, repl, mocker):
        """A line entered at the prompt is executed."""
        instance, recorder = repl
        mocker.patch(
            "exosphere.repl.prompt", side_effect=["inventory status", EOFError]
        )

        instance.cmdloop()

        assert ("status", SortField.host) in recorder

    def test_loop_recovers_from_unexpected_error(self, repl, mocker, capsys):
        """
        An unexpected error during a loop iteration (here from the prompt
        itself) is caught and reported; the loop keeps going rather than
        crashing out.
        """
        instance, _ = repl
        mocker.patch(
            "exosphere.repl.prompt", side_effect=[RuntimeError("OHNOES"), EOFError]
        )

        instance.cmdloop()

        out = capsys.readouterr().out
        assert "Unexpected error in REPL" in out
        # Reaching the EOF message proves the loop continued past the error.
        assert "Exiting" in out

    @pytest.mark.parametrize(
        "inputs, expected_message",
        [
            ([EOFError], "Exiting"),
            ([KeyboardInterrupt, EOFError], "Aborted"),  # Exit after ^C
        ],
        ids=["ctrl_d_exits", "ctrl_c_aborts"],
    )
    def test_control_signal_is_handled(
        self, repl, mocker, capsys, inputs, expected_message
    ):
        """
        Signals like ^C and ^D should be handled properly

        All tests rely on raising EOFError to exit the loop after the
        command is sent, so that may be slightly Extra(tm) here, but
        this test also validates the presentation of it (displayed
        message, no unexpected tracebacks, etc).
        """
        instance, _ = repl
        mocker.patch("exosphere.repl.prompt", side_effect=inputs)

        instance.cmdloop()

        assert expected_message in capsys.readouterr().out
