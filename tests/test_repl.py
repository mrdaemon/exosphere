"""
Tests for the REPL module
"""

import tempfile
from pathlib import Path

import click
import pytest
from prompt_toolkit.history import FileHistory, InMemoryHistory
from typer import Context

from exosphere.repl import ExosphereCompleter, ExosphereREPL


class TestExosphereCompleter:
    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("", {"help", "exit", "quit", "clear"}),
            ("he", {"help"}),
            ("ex", {"exit"}),
            ("qu", {"quit"}),
            ("cle", {"clear"}),
        ],
        ids=["all", "help", "exit", "quit", "clear"],
    )
    def test_get_completions_builtin_commands(self, input_text, expected):
        """
        Test completion of built-in commands (no root_command)
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        completer = ExosphereCompleter(None)
        completions = set(
            c.text
            for c in completer.get_completions(Document(input_text), CompleteEvent())
        )
        assert completions == expected or expected.issubset(completions)

    def test_get_completions_limit_matches(self, mocker):
        """
        Test that more than 8 matches returns nothing (limit logic)
        """
        from prompt_toolkit.document import Document

        many = [f"cmd{i}" for i in range(10)]
        mock_root = mocker.Mock()
        mock_root.commands = {n: mocker.Mock() for n in many}

        completer = ExosphereCompleter(mock_root)

        # Patch commands to be >8 and all start with 'cmd'
        completer.commands = many + ["help", "exit", "quit", "clear"]

        from prompt_toolkit.completion import CompleteEvent

        completions = list(completer.get_completions(Document("cmd"), CompleteEvent()))

        assert completions == []

    def test_get_completions_root_subcommands(self, mocker):
        """
        Test completion of subcommands from root_command
        """
        from prompt_toolkit.document import Document

        mock_root = mocker.Mock()
        mock_root.commands = {"foo": mocker.Mock(), "bar": mocker.Mock()}
        completer = ExosphereCompleter(mock_root)
        from prompt_toolkit.completion import CompleteEvent

        completions = set(
            c.text for c in completer.get_completions(Document("f"), CompleteEvent())
        )

        assert "foo" in completions
        assert "bar" not in completions

    def test_get_completions_help_subcommands(self, mocker):
        """
        Test that 'help ' suggests subcommands from root_command
        """
        from prompt_toolkit.document import Document

        mock_root = mocker.Mock()
        mock_root.commands = {"foo": mocker.Mock(), "bar": mocker.Mock()}
        completer = ExosphereCompleter(mock_root)
        doc = Document("help f")
        from prompt_toolkit.completion import CompleteEvent

        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )

        assert "foo" in completions
        assert "bar" not in completions

    def test_get_completions_subcommand_options(self, mocker):
        """
        Test completion of options for sub-subcommands
        """
        from prompt_toolkit.document import Document

        # Mock subsubcommand with params
        param = mocker.Mock()
        param.opts = ["--opt1", "--opt2", "-o"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"baz": subsub}
        root = mocker.Mock()
        root.commands = {"foo": sub}

        completer = ExosphereCompleter(root)

        # Should suggest --opt1, --opt2, --help
        doc = Document("foo baz --")
        from prompt_toolkit.completion import CompleteEvent

        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )

        assert "--opt1" in completions
        assert "--opt2" in completions
        assert "--help" in completions
        assert "-o" not in completions  # flags/options should not be suggested

    def test_get_completions_subcommand_options_no_repeat(self, mocker):
        """
        Test that options already present in the input are not repeated in completions
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        param = mocker.Mock()
        param.opts = ["--opt1", "--opt2", "-o"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"baz": subsub}
        root = mocker.Mock()
        root.commands = {"foo": sub}

        completer = ExosphereCompleter(root)

        # --opt1 is already present, should not be suggested again
        doc = Document("foo baz --opt1 --")
        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )
        assert "--opt1" not in completions
        assert "--opt2" in completions
        assert "--help" in completions

    def test_get_completions_simple_command_help(self, mocker):
        """
        Test that --help is suggested for simple commands
        """
        from prompt_toolkit.document import Document

        sub = mocker.Mock()
        sub.commands = {}
        root = mocker.Mock()
        root.commands = {"foo": sub}
        completer = ExosphereCompleter(root)
        doc = Document("foo --")
        from prompt_toolkit.completion import CompleteEvent

        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )
        assert "--help" in completions

    def test_get_completions_no_root_command(self):
        """
        Test that no completions are returned if no root_command and not builtin
        """
        from prompt_toolkit.document import Document

        completer = ExosphereCompleter(None)
        doc = Document("unknown ")
        from prompt_toolkit.completion import CompleteEvent

        completions = list(completer.get_completions(doc, CompleteEvent()))
        assert completions == []

    def test_completer_init_no_root_command(self):
        """
        Test that the completer initializes with default commands
        """
        completer = ExosphereCompleter(None)
        assert set(["help", "exit", "quit"]).issubset(set(completer.commands))

    def test_completer_init_with_root_command(self, mocker):
        """
        Test that the completer initializes with the root command's subcommands
        """
        mock_command = mocker.Mock()
        mock_command.commands = {"test": mocker.Mock(), "example": mocker.Mock()}

        completer = ExosphereCompleter(mock_command)

        assert "test" in completer.commands
        assert "example" in completer.commands


class TestExosphereREPL:
    def test_repl_init_defaults(self, mocker):
        """
        Test that the REPL initializes with default values
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        assert repl.ctx == ctx
        assert repl.prompt_text == "exosphere> "
        assert repl.console is not None
        assert repl.history is not None
        assert repl.completer is not None

    def test_repl_init_custom_prompt(self, mocker):
        """
        Test that the REPL can eat a custom prompt
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx, "custom> ")

        assert repl.prompt_text == "custom> "

    def test_setup_history_success(self, mocker):
        """
        Test that the REPL initializes with the history
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        tmpdir = tempfile.TemporaryDirectory()
        state_dir = Path(tmpdir.name)

        mocker.patch("exosphere.fspaths.ensure_dirs")
        mocker.patch("exosphere.fspaths.STATE_DIR", state_dir)

        repl = ExosphereREPL(ctx)

        assert isinstance(repl.history, FileHistory)

        tmpdir.cleanup()

    def test_setup_history_fallback(self, mocker, caplog):
        """
        Test that the REPL falls back to in-memory history on failure
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        mocker.patch("exosphere.fspaths.ensure_dirs", side_effect=Exception("fail"))

        with caplog.at_level("WARNING", logger="exosphere.repl"):
            repl = ExosphereREPL(ctx)

        assert isinstance(repl.history, InMemoryHistory)
        assert any("Could not setup persistent history" in m for m in caplog.messages)

    @pytest.mark.parametrize("cmd", ["exit", "quit"])
    def test_execute_command_exit(self, mocker, cmd):
        """
        Test the various exit commands.
        They all raise EOFError.
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        with pytest.raises(EOFError):
            repl.execute_command(cmd)

    def test_execute_command_help(self, mocker):
        """
        Test the built-in help command
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("help")

        assert any(
            any(
                s
                and (
                    "Available modules during interactive use" in str(s)
                    or "for help on a specific command." in str(s)
                )
                for s in call.args
            )
            for call in print_spy.call_args_list
        )

    def test_execute_command_help_general(self, mocker):
        """
        Test that 'help' with no arguments prints general help and builtins.
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")
        repl.execute_command("help")

        # Should mention built-in commands and usage
        assert any(
            call.args and "built-in commands" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )
        assert any(
            call.args and "use '<command> --help'" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

    @pytest.mark.parametrize(
        "cmd,expected_help",
        [
            ("clear", "clear the console"),
            ("quit", "exit the interactive shell"),
            ("exit", "exit the interactive shell"),
        ],
        ids=["clear", "quit", "exit"],
    )
    def test_execute_command_help_builtin(self, mocker, cmd, expected_help):
        """
        Test that 'help <builtin>' prints the builtin help for each builtin command.
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")
        repl.execute_command(f"help {cmd}")

        assert any(
            "built-in" in str(call.args[0]).lower()
            and expected_help in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

    def test_execute_command_help_typer_command(self, mocker):
        """
        Test help for Typer Commands
        The repl is expected to just wrap the the command with '--help' and
        its very specific context to delegate this to the Typer help system.
        """
        ctx = mocker.Mock(spec=Context)
        mock_sub = mocker.Mock()
        ctx.command = mocker.Mock()
        ctx.command.commands = {"test_command": mock_sub}
        repl = ExosphereREPL(ctx)

        # Patch make_context to yield a context manager that returns a dummy context
        dummy_ctx_mgr = mocker.MagicMock()
        dummy_ctx_mgr.__enter__.return_value = mocker.Mock()
        dummy_ctx_mgr.__exit__.return_value = False
        mock_sub.make_context.return_value = dummy_ctx_mgr

        repl.execute_command("help test_command")

        mock_sub.make_context.assert_called_once_with("test_command", ["--help"])
        mock_sub.invoke.assert_called_once_with(dummy_ctx_mgr.__enter__.return_value)

    def test_help_help(self, mocker):
        """
        Test that the help command provides help for itself
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("help help")

        assert any(
            "Use 'help' without arguments for general help." in str(call.args[0])
            for call in print_spy.call_args_list
        )

    def test_execute_command_empty(self, mocker):
        """
        Test that empty commands are handled gracefully
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        try:
            repl.execute_command("")
            repl.execute_command("   ")
        except Exception as e:
            pytest.fail(f"Empty command raised an exception: {e}")

    def test_execute_command_unknown(self, mocker):
        """
        Test that unknown commands are handled gracefully
        """
        mock_command = mocker.Mock()
        mock_command.commands = {"known": mocker.Mock()}

        ctx = mocker.Mock(spec=Context)
        ctx.command = mock_command

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("unknown")

        assert any(
            "Unknown command" in str(call.args[0]) for call in print_spy.call_args_list
        )

    def test_execute_command_no_root(self, mocker):
        """
        Test that whatever happens when the root command is unset is not a disaster
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("foobar")

        assert any(
            "No root command" in str(call.args[0]) for call in print_spy.call_args_list
        )

    def test_execute_command_known(self, mocker):
        """
        Test that a command executes
        """
        # Simulate a known command with a subcommand that runs without error
        mock_sub = mocker.MagicMock()
        mock_sub.invoke.return_value = None
        mock_command = mocker.Mock()
        mock_command.commands = {"foo": mock_sub}

        ctx = mocker.Mock(spec=Context)
        ctx.command = mock_command

        repl = ExosphereREPL(ctx)

        try:
            repl.execute_command("foo")
        except Exception as e:
            pytest.fail(f"Known command raised an exception: {e}")

    def test_execute_command_typer_noargs_is_help(self, mocker):
        """
        Test handling of NoArgsIsHelpError in typer commands
        Typer commands that are invoked without args are mostly all configured
        to show help, but also raise a NoArgsIsHelpError.
        """
        mock_sub = mocker.Mock()

        # Simulate the NoArgsIsHelpError being raised when invoking a command
        dummy_ctx_mgr = mocker.MagicMock()
        dummy_ctx_mgr.__enter__.return_value = mocker.Mock()
        dummy_ctx_mgr.__exit__.return_value = False
        mock_sub.make_context.return_value = dummy_ctx_mgr

        # Mock context manager for fake typer command
        # Ensure it raises NoArgsIsHelpError
        dummy_ctx = mocker.Mock()
        mock_sub.invoke.side_effect = click.exceptions.NoArgsIsHelpError(dummy_ctx)

        mock_command = mocker.Mock()
        mock_command.commands = {"foo": mock_sub}

        ctx = mocker.Mock(spec=Context)
        ctx.command = mock_command

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")
        repl.execute_command("foo")

        assert any(
            "requires arguments" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

    def test_execute_command_systemexit(self, mocker):
        """
        Test that a command that raises SystemExit is handled gracefully
        Normally commands should raise a typer exit exception, but we should
        handle when they don't gracefully.
        """
        mock_sub = mocker.MagicMock()
        mock_sub.invoke.side_effect = SystemExit(1)
        mock_command = mocker.Mock()
        mock_command.commands = {"foo": mock_sub}

        ctx = mocker.Mock(spec=Context)
        ctx.command = mock_command

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        try:
            repl.execute_command("foo")
        except Exception:
            pytest.fail("execute_command raised an exception unexpectedly")

        assert any(
            "Command exited with code" in str(call.args[0])
            for call in print_spy.call_args_list
        )

    def test_execute_command_unexpected_exception(self, mocker):
        """
        Test unexpected exceptions during command execution
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        # Patch shlex.split to raise an unexpected exception
        mocker.patch("shlex.split", side_effect=RuntimeError("unexpected error yo"))
        print_spy = mocker.spy(repl.console, "print")

        try:
            repl.execute_command("foo")
        except Exception:
            pytest.fail("execute_command raised an exception unexpectedly")

        assert any(
            "unexpected error yo" in str(call.args[0]).lower()
            or "error" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

    def test_execute_command_parsing_error(self, mocker):
        """
        Test that parsing errors are handled gracefully
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        # Patch shlex.split to raise a ValueError
        mocker.patch("shlex.split", side_effect=ValueError("Megafailure Event"))

        print_spy = mocker.spy(repl.console, "print")

        try:
            repl.execute_command("foo")
        except Exception:
            pytest.fail("execute_command raised an exception unexpectedly")

        assert any(
            "error parsing command" in str(call.args[0]).lower()
            and "megafailure event" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

    @pytest.mark.parametrize(
        "side_effect,expected",
        [
            ([KeyboardInterrupt, EOFError], "Aborted"),
            ([EOFError], "Exiting Interactive mode"),
            ([Exception("fail"), EOFError], "Unexpected error in REPL"),
        ],
    )
    def test_cmdloop_exceptions(self, mocker, side_effect, expected):
        """
        Test cmdloop handles various expected and unexpected exceptions
        And also always exits.
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        mocker.patch("exosphere.repl.prompt", side_effect=side_effect)
        print_spy = mocker.spy(repl.console, "print")

        repl.cmdloop()
        assert any(expected in str(call.args[0]) for call in print_spy.call_args_list)

    def test_cmdloop_ignores_whitespace_only_input(self, mocker):
        """
        Test that whitespace-only input is ignored and does not call execute_command
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        # Simulate whitespace input, then EOFError to exit
        mocker.patch("exosphere.repl.prompt", side_effect=["   ", EOFError])
        exec_mock = mocker.patch.object(repl, "execute_command")

        repl.cmdloop()

        # execute_command should not be called for whitespace input
        exec_mock.assert_not_called()

    def test_cmdloop_intro_message(self, mocker):
        """
        Test that the intro message is displayed at the start of the REPL loop
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        # Simulate an EOFError input to exit the loop immediately
        mocker.patch("exosphere.repl.prompt", side_effect=EOFError)
        print_spy = mocker.spy(repl.console, "print")

        repl.cmdloop(intro="Welcome to Exosphere!")
        assert any(
            "Welcome to Exosphere!" in str(call.args[0])
            for call in print_spy.call_args_list
        )

    def test_cmdloop_clear_command_clears_console(self, mocker):
        """
        Test that entering 'clear' in the REPL loop calls console.clear()
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None
        repl = ExosphereREPL(ctx)

        # Patch prompt to return 'clear' then EOFError to exit
        mocker.patch("exosphere.repl.prompt", side_effect=["clear", EOFError])
        clear_mock = mocker.patch.object(repl.console, "clear")

        repl.cmdloop()
        clear_mock.assert_called_once()
