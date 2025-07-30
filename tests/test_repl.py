"""
Tests for the REPL module
"""

import tempfile
from pathlib import Path

import pytest
from prompt_toolkit.history import FileHistory, InMemoryHistory
from typer import Context

from exosphere.repl import ExosphereCompleter, ExosphereREPL


class TestExosphereCompleter:
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

        repl.execute_command("foo")

        assert any(
            "Command exited with code" in str(call.args[0])
            for call in print_spy.call_args_list
        )
