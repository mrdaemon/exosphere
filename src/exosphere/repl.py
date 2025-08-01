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

logger = logging.getLogger(__name__)


class ExosphereCompleter(Completer):
    """
    Readline-like completion for Exosphere Commands
    """

    def __init__(self, root_command):
        self.root_command = root_command
        self.commands = ["clear", "help", "exit", "quit"]
        if root_command:
            self.commands += list(getattr(root_command, "commands", {}))

    def get_completions(self, document: Document, complete_event):
        """
        Retrieve completions based on current input

        Provides the main completer logic for Exosphere commands.

        :param document: The current input document
        :param complete_event: The completion event (not used here)
        """
        text = document.text_before_cursor
        words = text.split()

        # Basic completion logic
        if not words or (len(words) == 1 and not text.endswith(" ")):
            # Main command completion
            prefix = words[0].lower() if words else ""
            matches = [c for c in self.commands if c.lower().startswith(prefix)]

            # We arbitrarily limit the number of matches to 8
            # and just kind of silently bail.
            if prefix and len(matches) > 8:
                return

            for match in matches:
                sp = -len(words[0]) if words and prefix else 0
                yield Completion(match, start_position=sp)
            return

        # Handle built-in commands
        command = words[0]
        if command in ("help", "exit", "quit"):
            if command == "help" and len(words) <= 2:
                # Help should suggest subcommands
                if self.root_command:
                    main_commands = getattr(self.root_command, "commands", {})
                    current = words[1] if len(words) > 1 else ""
                    for name in main_commands:
                        if name.startswith(current):
                            yield Completion(name, start_position=-len(current))
            return

        # Handle exosphere commands off the root command
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
        # This kind of a hack, but it's enough for our needs so far
        used_opts = set(w for w in words[1:] if w.startswith("-"))

        current = words[-1] if not text.endswith(" ") else ""
        sp = -len(current) if current else 0

        # Group: complete subcommands
        if hasattr(subcommand, "commands") and subcommand.commands:
            if len(words) == 1 or (len(words) == 2 and not text.endswith(" ")):
                for name in subcommand.commands:
                    if name.startswith(current):
                        yield Completion(name, start_position=sp)
            elif len(words) >= 2:
                subsub = subcommand.commands.get(words[1])
                if subsub and hasattr(subsub, "params"):
                    opts = {"--help"}
                    for param in subsub.params:
                        if hasattr(param, "opts"):
                            # Only add options that look like gnu long options
                            opts.update(o for o in param.opts if o.startswith("--"))

                    # Filter out already used options
                    for opt in opts:
                        if opt not in used_opts and opt.startswith(current):
                            yield Completion(opt, start_position=sp)
        else:
            # We helpfully tack on --help to simple commands because
            # it is universal to typer commands
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
            logger.warning(f"Could not setup persistent history: {e}")
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
                user_input = prompt(
                    prompt_html,
                    history=self.history,
                    completer=self.completer,
                    complete_while_typing=False,
                    enable_history_search=True,
                    complete_style=CompleteStyle.READLINE_LIKE,  # Use readline-style completion
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
                lines.append(f"[cyan]{name:<11}[/cyan] {help_text}")

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
