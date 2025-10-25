"""
Tests for the REPL module
"""

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

    def test_get_completions_host_positional_arg(self, mocker):
        """
        Test completion of host names for positional arguments
        (e.g., 'host show <TAB>')
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock the inventory context
        mock_host1 = mocker.Mock()
        mock_host1.name = "webserver"
        mock_host2 = mocker.Mock()
        mock_host2.name = "dbserver"
        mock_host3 = mocker.Mock()
        mock_host3.name = "appserver"

        mock_inventory = mocker.Mock()
        mock_inventory.hosts = [mock_host1, mock_host2, mock_host3]

        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = mock_inventory

        # Mock command structure
        param = mocker.Mock()
        param.opts = ["--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"show": subsub}
        root = mocker.Mock()
        root.commands = {"host": sub}

        completer = ExosphereCompleter(root)

        # Test completing host names after "host show "
        doc = Document("host show ")
        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )

        assert "webserver" in completions
        assert "dbserver" in completions
        assert "appserver" in completions

    def test_get_completions_host_positional_arg_prefix(self, mocker):
        """
        Test completion of host names with prefix matching
        (e.g., 'host show web<TAB>')
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock the inventory context
        mock_host1 = mocker.Mock()
        mock_host1.name = "webserver"
        mock_host2 = mocker.Mock()
        mock_host2.name = "web-staging"
        mock_host3 = mocker.Mock()
        mock_host3.name = "dbserver"

        mock_inventory = mocker.Mock()
        mock_inventory.hosts = [mock_host1, mock_host2, mock_host3]

        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = mock_inventory

        # Mock command structure
        param = mocker.Mock()
        param.opts = ["--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"show": subsub}
        root = mocker.Mock()
        root.commands = {"host": sub}

        completer = ExosphereCompleter(root)

        # Test completing host names with "web" prefix
        doc = Document("host show web")
        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )

        assert "webserver" in completions
        assert "web-staging" in completions
        assert "dbserver" not in completions

    @pytest.mark.parametrize(
        "option_flag,expected_hosts",
        [
            ("--host", {"server1", "server2"}),
            ("-h", {"server1", "server2"}),
        ],
        ids=["long-form", "short-form"],
    )
    def test_get_completions_host_option_value(
        self, mocker, option_flag, expected_hosts
    ):
        """
        Test completion of host names for option values
        (e.g., 'sudo generate --host <TAB>' or 'sudo generate -h <TAB>')
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock the inventory context
        mock_host1 = mocker.Mock()
        mock_host1.name = "server1"
        mock_host2 = mocker.Mock()
        mock_host2.name = "server2"

        mock_inventory = mocker.Mock()
        mock_inventory.hosts = [mock_host1, mock_host2]

        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = mock_inventory

        # Mock command structure
        param = mocker.Mock()
        param.opts = ["--host", "-h", "--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"generate": subsub}
        root = mocker.Mock()
        root.commands = {"sudo": sub}

        completer = ExosphereCompleter(root)

        # Test completing host names after option flag
        doc = Document(f"sudo generate {option_flag} ")
        completions = set(
            c.text for c in completer.get_completions(doc, CompleteEvent())
        )

        assert completions == expected_hosts

    def test_get_completions_no_hosts_in_inventory(self, mocker):
        """
        Test that completion works gracefully when inventory is empty
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock empty inventory
        mock_inventory = mocker.Mock()
        mock_inventory.hosts = []

        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = mock_inventory

        # Mock command structure
        param = mocker.Mock()
        param.opts = ["--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"show": subsub}
        root = mocker.Mock()
        root.commands = {"host": sub}

        completer = ExosphereCompleter(root)

        # Should return no completions but not crash
        doc = Document("host show ")
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert completions == []

    def test_get_completions_no_inventory_context(self, mocker):
        """
        Test that completion works gracefully when inventory context is None
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock None inventory
        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = None

        # Mock command structure
        param = mocker.Mock()
        param.opts = ["--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"show": subsub}
        root = mocker.Mock()
        root.commands = {"host": sub}

        completer = ExosphereCompleter(root)

        # Should return no completions but not crash
        doc = Document("host show ")
        completions = list(completer.get_completions(doc, CompleteEvent()))

        assert completions == []

    def test_get_completions_no_host_completion_for_unknown_options(self, mocker):
        """
        Ensure we do not complete hosts for options that don't expect them.
        For example, 'report generate --format <TAB>' should not suggest hosts,
        even though it takes them as positionals later.
        """
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        # Mock the inventory context with some hosts
        mock_host1 = mocker.Mock()
        mock_host1.name = "server1"
        mock_host2 = mocker.Mock()
        mock_host2.name = "server2"

        mock_inventory = mocker.Mock()
        mock_inventory.hosts = [mock_host1, mock_host2]

        mocker.patch("exosphere.repl.app_context")
        from exosphere import repl

        repl.app_context.inventory = mock_inventory

        # Mock command structure for 'report generate' with --format option
        param = mocker.Mock()
        param.opts = ["--format", "-f", "--help"]
        subsub = mocker.Mock()
        subsub.params = [param]
        sub = mocker.Mock()
        sub.commands = {"generate": subsub}
        root = mocker.Mock()
        root.commands = {"report": sub}

        completer = ExosphereCompleter(root)

        # Test that after "--format " we don't get host completions
        doc = Document("report generate --format ")
        completions = list(completer.get_completions(doc, CompleteEvent()))

        # Should return no completions (we don't know what --format expects)
        assert completions == []

        # Verify we're not accidentally suggesting hosts
        completion_texts = [c.text for c in completions]
        assert "server1" not in completion_texts
        assert "server2" not in completion_texts


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

    def test_setup_history_fallback(self, mocker, caplog):
        """
        Test that the REPL falls back to in-memory history on failure
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        mocker.patch("exosphere.repl.FileHistory", side_effect=Exception("fail"))

        with caplog.at_level("WARNING", logger="exosphere.repl"):
            repl = ExosphereREPL(ctx)

        assert isinstance(repl.history, InMemoryHistory)
        assert any("Could not setup persistent history" in m for m in caplog.messages)

    def test_setup_history_from_config(self, mocker, tmp_path):
        """
        Test that the REPL initializes with history path from config
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = None

        from exosphere.config import Configuration

        config = Configuration()

        test_history_file = str(tmp_path / "test_history_path")

        conf_data = {
            "options": {
                "history_file": test_history_file,
            }
        }

        config.update_from_mapping(conf_data)
        mocker.patch("exosphere.repl.app_config", config)

        repl = ExosphereREPL(ctx)

        assert isinstance(repl.history, FileHistory)
        assert repl.history.filename == test_history_file

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

    def test_execute_command_help_general_with_commands(self, mocker):
        """
        Test that 'help' with no arguments lists available commands on root
        """
        ctx = mocker.Mock(spec=Context)

        # Mock commands with help text
        mock_cmd1 = mocker.Mock()
        mock_cmd1.help = "Manage host configurations"
        mock_cmd1.hidden = False

        mock_cmd2 = mocker.Mock()
        mock_cmd2.help = "Display inventory information"
        mock_cmd2.hidden = False

        mock_cmd3 = mocker.Mock()
        mock_cmd3.help = "Hidden command"
        mock_cmd3.hidden = True

        ctx.command = mocker.Mock()
        ctx.command.commands = {
            "host": mock_cmd1,
            "inventory": mock_cmd2,
            "hidden": mock_cmd3,
        }

        repl = ExosphereREPL(ctx)
        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("help")

        # Should print available modules header
        assert any(
            call.args and "available modules" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

        # Should show usage instructions
        assert any(
            call.args and "use '<command> --help'" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
        )

        # Verify that a Panel was printed (contains the commands)
        from rich.panel import Panel

        assert any(
            isinstance(call.args[0], Panel)
            for call in print_spy.call_args_list
            if call.args
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
        mock_command.commands = {"known": mocker.Mock(), "another": mocker.Mock()}

        ctx = mocker.Mock(spec=Context)
        ctx.command = mock_command

        repl = ExosphereREPL(ctx)

        print_spy = mocker.spy(repl.console, "print")

        repl.execute_command("unknown")

        assert any(
            "Unknown command" in str(call.args[0]) for call in print_spy.call_args_list
        )

        # Should also list available commands
        assert any(
            "available commands" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
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

    def test_execute_command_no_args_with_root(self, mocker):
        """
        Test that calling _execute_typer_command with empty args prints an error.
        """
        ctx = mocker.Mock(spec=Context)
        ctx.command = mocker.Mock()
        ctx.command.commands = {"foo": mocker.Mock()}

        repl = ExosphereREPL(ctx)
        print_spy = mocker.spy(repl.console, "print")

        # Call _execute_typer_command directly with empty list
        repl._execute_typer_command([])

        assert any(
            "no command specified" in str(call.args[0]).lower()
            for call in print_spy.call_args_list
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

    def test_execute_command_general_exception(self, mocker):
        """
        Test that general exceptions during command execution are handled gracefully.
        """
        ctx = mocker.Mock(spec=Context)
        mock_sub = mocker.Mock()
        ctx.command = mocker.Mock()
        ctx.command.commands = {"failing_cmd": mock_sub}

        repl = ExosphereREPL(ctx)

        # Mock make_context to raise a general exception
        mock_sub.make_context.side_effect = RuntimeError(
            "Something went horribly wrong"
        )

        print_spy = mocker.spy(repl.console, "print")

        # Should not raise, should handle gracefully
        try:
            repl.execute_command("failing_cmd")
        except Exception:
            pytest.fail("execute_command raised an exception unexpectedly")

        # Should print error message
        assert any(
            "error executing failing_cmd" in str(call.args[0]).lower()
            and "something went horribly wrong" in str(call.args[0]).lower()
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
