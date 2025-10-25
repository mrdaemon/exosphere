"""
REPL module for Exosphere

This module implements the Exosphere REPL, providing enhanced features
like command history, autocompletion, and better line editing while
maintaining Rich output formatting.
"""

import logging
import shlex

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.panel import Panel
from typer import Context

from exosphere import app_config
from exosphere import context as app_context

logger = logging.getLogger(__name__)


class ExosphereCompleter(Completer):
    """
    Readline-like completion for Exosphere Commands

    Handles completion of:

     - Top-level commands (host, inventory, sudo, etc.)
     - Subcommands and their options
     - Sub-subcommands and their options
     - Host name completions for relevant commands
     - Host name completion for options that accept them
     - Built-in commands like help, exit, clear

    """

    # We hardcode some stuff for host name completion here.
    # In a perfect world we would extract this from Typer commands,
    # but we already do this in two different places in the codebase
    # (including documentation generation). I'm just tired, boss.

    # Commands that take host names as positional arguments
    # Maps command paths to which argument positions accept host names
    # Keys can be nested for subcommands
    HOST_ARG_COMMANDS = {
        "host": {
            "show": [0],  # host show <name>
            "ping": [0],  # host ping <name>
            "discover": [0],  # host discover <name>
            "refresh": [0],  # host refresh <name>
        },
        "inventory": {
            "ping": [0],  # inventory ping [names...]
            "discover": [0],  # inventory discover [names...]
            "refresh": [0],  # inventory refresh [names...]
            "status": [0],  # inventory status [names...]
        },
        "report": {
            "generate": [0],  # report generate [names...]
        },
        "sudo": {
            "check": [0],  # sudo check <name>
        },
    }

    # Commands that take host names as option values (e.g., --host <name>)
    # Maps command paths to option names that accept host names
    HOST_OPTION_COMMANDS = {
        "sudo": {
            "generate": ["--host", "-h"],  # sudo generate --host <name>
        },
    }

    def __init__(self, root_command):
        self.root_command = root_command
        self.commands = ["clear", "help", "exit", "quit"]
        if root_command:
            self.commands += list(getattr(root_command, "commands", {}))

    def _get_host_names(self) -> list[str]:
        """Get list of host names from current inventory."""
        if app_context.inventory is None:
            return []

        return [host.name for host in app_context.inventory.hosts]

    def _make_completions(
        self, matches: list[str], start_position: int
    ) -> list[Completion]:
        """
        Return Completion objects for the given matches.

        We append a space on full match for rapid tab-through completion,
        an ancestral behavior from Quality Things like bash that I, for one,
        absolutely expect.
        """
        if len(matches) == 1:
            return [Completion(matches[0] + " ", start_position=start_position)]

        return [Completion(match, start_position=start_position) for match in matches]

    def _complete_main_commands(self, words: list[str], text: str) -> list[Completion]:
        """Complete top-level commands (host, inventory, sudo, etc.)."""
        prefix = words[0].lower() if words else ""
        matches = [c for c in self.commands if c.lower().startswith(prefix)]

        # We arbitrarily limit the number of matches to 8
        # and just kind of silently bail if exceeded.
        if prefix and len(matches) > 8:
            return []

        sp = -len(words[0]) if words and prefix else 0
        return self._make_completions(matches, sp)

    def _complete_help_command(self, words: list[str]) -> list[Completion]:
        """Complete the 'help' builtin command with available commands."""
        if not self.root_command:
            return []

        main_commands = getattr(self.root_command, "commands", {})
        current = words[1] if len(words) > 1 else ""
        matching = [name for name in main_commands if name.startswith(current)]

        return self._make_completions(matching, -len(current))

    def _should_complete_host_option_value(
        self, command: str, words: list[str], text: str
    ) -> bool:
        """
        Check if we can and should complete host names for an option value.

        Has some extra sanity checks, for current state, but mainly just
        checks if the option is in the HOST_OPTION_COMMANDS mapping.
        """

        if len(words) < 2:
            return False

        # Ensure we're not still completing the option itself by expecting
        # a space in the unsplit text.
        prev_option = (
            words[-1] if text.endswith(" ") else (words[-2] if len(words) >= 2 else "")
        )

        if not prev_option.startswith("-"):
            return False

        if command not in self.HOST_OPTION_COMMANDS:
            return False

        subcmd_config = self.HOST_OPTION_COMMANDS[command]
        if not isinstance(subcmd_config, dict) or words[1] not in subcmd_config:
            return False

        host_options = subcmd_config[words[1]]
        return prev_option in host_options

    def _complete_host_names(self, current: str, sp: int) -> list[Completion]:
        """Return host name completions."""
        host_names = self._get_host_names()
        matching = [h for h in host_names if h.startswith(current)]
        return self._make_completions(matching, sp)

    def _complete_host_positional_arg(
        self, command: str, words: list[str], text: str, current: str, sp: int
    ):
        """Complete host names for positional arguments."""
        if command not in self.HOST_ARG_COMMANDS:
            return

        subcmd_config = self.HOST_ARG_COMMANDS[command]
        if not isinstance(subcmd_config, dict) or words[1] not in subcmd_config:
            return

        # Count non-option arguments to determine position
        non_opt_args = [w for w in words[2:] if not w.startswith("-")]
        arg_position = (
            len(non_opt_args) if text.endswith(" ") else len(non_opt_args) - 1
        )

        positions = subcmd_config[words[1]]
        if arg_position in positions or positions == [0]:  # [0] means all positions
            yield from self._complete_host_names(current, sp)

    def _is_flag_option(self, subsub, option_name: str) -> bool:
        """
        Check if an option is a flag (doesn't take a value).

        This is used to determine whether or not to halt completion after
        an option is completed.
        """
        if not hasattr(subsub, "params"):
            return False

        # We check for Click/Typer is_flag, count, and BOOL type
        # All of them imply the option value is themselves (a flag)
        for param in subsub.params:
            if hasattr(param, "opts") and option_name in param.opts:
                if getattr(param, "is_flag", False):
                    return True
                if getattr(param, "count", False):
                    return True
                if (
                    hasattr(param, "type")
                    and getattr(param.type, "name", None) == "BOOL"
                ):
                    return True

        return False

    def _complete_subsubcommand(
        self, command: str, subcommand, words: list[str], text: str, used_opts: set
    ):
        """
        Complete options and arguments for a subsubcommand
        (e.g., 'host show').

        This is where most of the hot complete action happens within
        the context of Exosphere.
        """
        subsub = subcommand.commands.get(words[1])
        if not subsub or not hasattr(subsub, "params"):
            return

        current = words[-1] if not text.endswith(" ") else ""
        sp = -len(current) if current else 0

        # Complete options if current word starts with -
        # (e.g., typing "--ho" to get "--host")
        if current.startswith("-"):
            opts = {"--help"}
            for param in subsub.params:
                if hasattr(param, "opts"):
                    opts.update(o for o in param.opts if o.startswith("--"))

            # Filter matching options
            matching_opts = [
                opt for opt in opts if opt not in used_opts and opt.startswith(current)
            ]

            yield from self._make_completions(matching_opts, sp)
            return

        # If previous word was an option that takes host names, complete host names
        if self._should_complete_host_option_value(command, words, text):
            yield from self._complete_host_names(current, sp)
            return

        # Stop completion if we are following an option flag that expects a value
        prev_word = (
            words[-1] if text.endswith(" ") else (words[-2] if len(words) >= 2 else "")
        )
        if prev_word.startswith("-") and not self._is_flag_option(subsub, prev_word):
            return

        # Complete host names for positional arguments
        yield from self._complete_host_positional_arg(command, words, text, current, sp)

    def get_completions(self, document: Document, complete_event):
        """
        Retrieve completions based on current input.

        Provides the main completer logic for Exosphere commands.

        :param document: The current input document
        :param complete_event: The completion event (not used here)
        """
        text = document.text_before_cursor
        words = text.split()

        # Complete top-level commands
        if not words or (len(words) == 1 and not text.endswith(" ")):
            yield from self._complete_main_commands(words, text)
            return

        # Handle built-in commands
        command = words[0]
        if command in ("help", "exit", "quit"):
            if command == "help" and len(words) <= 2:
                yield from self._complete_help_command(words)
            return

        # Handle exosphere commands from the root command
        # Typer commands are all attached to the root repl command
        # which dispatches them as subcommands -- which, surprise surprise,
        # will also have subcommands of their own.
        if not self.root_command:
            return

        main_commands = getattr(self.root_command, "commands", {})
        subcommand = main_commands.get(command)
        if not subcommand:
            return

        # Collect already used options to avoid repeating them
        # This is kind of a hack, but it's enough for our needs so far
        used_opts = set(w for w in words[1:] if w.startswith("-"))

        current = words[-1] if not text.endswith(" ") else ""
        sp = -len(current) if current else 0

        # Complete subcommands if available
        if hasattr(subcommand, "commands") and subcommand.commands:
            if len(words) == 1 or (len(words) == 2 and not text.endswith(" ")):
                matching = [
                    name for name in subcommand.commands if name.startswith(current)
                ]

                yield from self._make_completions(matching, sp)
            elif len(words) >= 2:
                yield from self._complete_subsubcommand(
                    command, subcommand, words, text, used_opts
                )
        else:
            # We helpfully tack on --help to simple commands because
            # it is universal to all typer commands.
            if "--help".startswith(current) and "--help" not in used_opts:
                yield Completion("--help", start_position=sp)


class ExosphereREPL:
    """
    REPL component for Exosphere

    Provides an interactive interface with enhanced features:
    - Command history with search (Ctrl+R)
    - Tab autocompletion down to subcommands and options
    - Cross-platform compatibility
    - And probably more as I start to regret my life choices
    """

    def __init__(self, ctx: Context, prompt_text: str = "exosphere> "):
        """
        Initialize the REPL with the given context and prompt.

        :param ctx: Typer/Click context
        :param prompt_text: The prompt string to display
        """
        self.ctx = ctx
        self.prompt_text = prompt_text
        self.console = Console()

        # Builtin commands, mostly for help
        self.builtins = {
            "exit": "Exit the interactive shell",
            "quit": "Exit the interactive shell",
            "clear": "Clear the console",
        }

        # Setup persistent history
        self.history = self._setup_history()

        # Get the root command for executing subcommands
        self.root_command = ctx.command if ctx.command else None

        # Setup the specialized completer
        self.completer = ExosphereCompleter(self.root_command)

    def _setup_history(self) -> FileHistory | InMemoryHistory:
        """
        Setup persistent command history using FileHistory

        The history file will be dumped in the State directory
        for exosphere, according to platform conventions.

        :return: FileHistory instance with proper file path,
                 or InMemoryHistory as fallback
        """
        try:
            history_file = app_config["options"]["history_file"]
            return FileHistory(str(history_file))
        except Exception as e:
            # Fallback to in-memory history if file operations fail
            logger.warning("Could not setup persistent history: %s", e)
            logger.warning("REPL is falling back to in-memory history")

            from prompt_toolkit.history import InMemoryHistory

            return InMemoryHistory()

    def cmdloop(self, intro: str | None = None) -> None:
        """
        Main REPL loop

        Handles printing the prompt and reading user input.
        """

        # Standard optional intro/banner subtext
        if intro:
            self.console.print(intro)
            self.console.print()

        # Use HTML to format the prompt since it's what prompt_toolkit expects
        # I would use Rich tags here this is a different animal.
        prompt_html = HTML(f"<ansiblue>{self.prompt_text}</ansiblue>")

        while True:
            try:
                # Prompt for user input with colored prompt
                # We use readline style completion for familiarity
                user_input = prompt(
                    prompt_html,
                    history=self.history,
                    completer=self.completer,
                    complete_while_typing=False,
                    enable_history_search=True,
                    complete_style=CompleteStyle.READLINE_LIKE,
                )

                if not user_input.strip():
                    continue

                # Execute the command
                self.execute_command(user_input.strip())

            except KeyboardInterrupt:
                # Ctrl+C cancels the current input and continues
                self.console.print("[dim]Aborted - Use ^D to exit[/dim]")
                continue
            except EOFError:
                # Ctrl+D exits gracefully
                self.console.print("Exiting Interactive mode")
                break
            except Exception as e:
                self.console.print(f"[red]Unexpected error in REPL: {e}[/red]")
                logger.exception("Unexpected error in REPL")

    def execute_command(self, line: str) -> None:
        """
        Execute a command with Rich output formatting
        """
        try:
            # Split the command line into arguments
            args = shlex.split(line)
            if not args:
                return

            command = args[0]

            # Handle built-in commands
            if command in ("exit", "quit"):
                raise EOFError
            elif command == "help":
                self._show_help(args[1:])
                return
            elif command == "clear":
                self.console.clear()
                return

            # Execute Typer/Click commands
            self._execute_typer_command(args)

        except ValueError as e:
            self.console.print(f"[red]Error parsing command: {e}[/red]")
        except (SystemExit, click.exceptions.Exit):
            # Commands may exit, this is expected
            pass
        except EOFError:
            # Re-raise EOFError so it reaches the main loop
            # Allows Ctrl+D to exit gracefully
            raise
        except Exception as e:
            self.console.print(f"[red]Error executing command: {e}[/red]")
            logger.exception(f"Error executing command: {line}")

    def _execute_typer_command(self, args: list[str]) -> None:
        """
        Execute a Typer/Click command through its explicit context

        We scope the context to the subcommand specifically in order to
        make the Typer help system not display the entire command tree
        in its usage line, which is cleaner, and also more useful in
        interactive mode.

        :param args: Command arguments
        """
        if not self.root_command or not args:
            if not self.root_command:
                self.console.print("[red]No root command available[/red]")
            else:
                self.console.print("[red]No command specified[/red]")
            return

        command_name = args[0]

        # Find the subcommand in the root command's commands dict
        subcommands = getattr(self.root_command, "commands", {})
        subcommand = subcommands.get(command_name)

        if not subcommand:
            self.console.print(f"[red]Unknown command: {command_name}[/red]")
            available = list(subcommands.keys())
            if available:
                self.console.print(f"Available commands: {', '.join(available)}")
            return

        # Create context without parent to avoid issues with help
        try:
            with subcommand.make_context(command_name, args[1:]) as sub_ctx:
                subcommand.invoke(sub_ctx)

        except click.exceptions.Exit:
            # Commands (including help) may exit, this is expected
            pass

        except click.exceptions.NoArgsIsHelpError:
            # Command was invoked with no arguments and displayed help
            self.console.print(f"[red]Command {command_name} requires arguments[/red]")

        except SystemExit as e:
            # Handle sys.exit calls from commands gracefully
            # In general, commands exit by raising Typer's specific exit state
            # But it's better to be defensive here, as to highlight bugs.
            if e.code is not None and e.code != 0:
                self.console.print(
                    f"[yellow]Command exited with code {e.code}[/yellow]"
                )

        except Exception as e:
            # Something went horribly wrong and we have no idea what
            self.console.print(f"[red]Error executing {command_name}: {e}[/red]")
            logger.exception(f"Error executing command '{command_name}': {e}")

    def _show_help(self, args: list) -> None:
        """
        Show help with Rich formatting
        """
        if not args:
            # General help
            self._show_general_help()
        elif args[0] in self.builtins:
            # Handle built-in commands
            self.console.print(f"[cyan]Built-in: {self.builtins[args[0]]}[/cyan]")
        elif args[0] == "--help" or args[0] == "help":
            # Show help for help, because someone is bound to try
            # Might as well leave a small easter egg for them.
            self.console.print(
                "[cyan]Yes, that is indeed how that works.[/cyan]\n"
                "Use 'help' without arguments for general help."
            )
        else:
            # Specific command help, we just wrap the command with
            # '--help' as argument and let the typer help system handle it
            self._execute_typer_command([args[0], "--help"])

    def _show_general_help(self) -> None:
        """
        Show general help for interactive mode
        """
        if self.root_command:
            subcommands = getattr(self.root_command, "commands", {})
            lines = []
            for name, cmd in subcommands.items():
                if getattr(cmd, "hidden", False):
                    continue
                help_text = getattr(cmd, "help", None) or "No description available."

                # Show only the first line of the help text for brevity
                # This can be a multi-line string
                first_line = help_text.split("\n")[0]

                lines.append(f"[cyan]{name:<11}[/cyan] {first_line}")

            if lines:
                content = "\n".join(lines)
                panel = Panel.fit(
                    content,
                    title="Commands",
                    title_align="left",
                )
                self.console.print("\nAvailable modules during interactive use:\n")
                self.console.print(panel)

        # Spacing for better readability
        self.console.print()

        self.console.print(
            "Use '<command> --help' or 'help <command>' for help on a specific command."
        )

        if self.builtins:
            # Show built-in commands
            self.console.print(
                f"[dim]Built-in commands: {', '.join(self.builtins.keys())}[/dim]"
            )
        else:
            # Leave empty line if no built-ins
            self.console.print()


def start_repl(ctx: Context, prompt_text: str = "exosphere> ") -> None:
    """
    Start the Exosphere REPL

    :param ctx: Click context
    :param prompt_text: The prompt string to display
    """
    repl = ExosphereREPL(ctx, prompt_text)
    intro = (
        "[cyan]Welcome to the Exosphere interactive shell[/cyan]\n"
        "Type 'help' for commands or 'ui start' to start the UI."
    )
    repl.cmdloop(intro=intro)
