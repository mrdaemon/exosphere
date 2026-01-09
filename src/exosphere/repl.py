"""
REPL module for Exosphere

This module implements the Exosphere REPL, providing enhanced features
like command history, autocompletion, and better line editing while
maintaining Rich output formatting.
"""

import inspect
import logging
import shlex
from collections.abc import Generator
from enum import Enum
from typing import Annotated, get_args, get_origin

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.panel import Panel
from typer import Context

from exosphere import app_config
from exosphere import context as app_context
from exosphere.commands.utils import HostArgument, HostOption

logger = logging.getLogger(__name__)


class HostMatchMode(Enum):
    """
    Defines how host name completion behaves for a command.

    SINGLE: Command accepts exactly one host at position 0
    MULTIPLE: Command accepts multiple hosts at any position
    """

    SINGLE = "single"
    MULTIPLE = "multiple"


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

    Host completion behavior is driven by metadata extracted from command
    annotations (HostArgument and HostOption) at initialization time.
    """

    def __init__(self, root_command: click.Command | None) -> None:
        self.root_command = root_command
        self.commands = ["clear", "help", "exit", "quit"]
        if root_command:
            self.commands += list(getattr(root_command, "commands", {}))

        # Extract host command metadata from annotations
        # We do this ahead of time, on init instead of on demand, for performance.
        arg_commands, option_commands = self._extract_host_metadata(root_command)
        self.HOST_ARG_COMMANDS = arg_commands
        self.HOST_OPTION_COMMANDS = option_commands

    def _extract_host_metadata(
        self, root_command: click.Command | None
    ) -> tuple[dict[str, dict[str, HostMatchMode]], dict[str, dict[str, list[str]]]]:
        """
        Extract host completion metadata from command annotations.

        We do this by introspecting the Click/Typer command signatures
        and looking for our custom HostArgument and HostOption annotations.
        """
        host_args = {}
        host_options = {}

        if not root_command:
            return host_args, host_options

        try:
            commands = getattr(root_command, "commands", {})
            for group_name, group_cmd in commands.items():
                self._extract_from_group(group_name, group_cmd, host_args, host_options)
        except (AttributeError, TypeError) as e:
            logger.debug("Could not extract host completion metadata: %s", e)

        return host_args, host_options

    def _extract_from_group(
        self,
        group_name: str,
        group_cmd: click.Command,
        host_args: dict[str, dict[str, HostMatchMode]],
        host_options: dict[str, dict[str, list[str]]],
    ) -> None:
        """Extract host completion metadata from a command group."""
        commands = getattr(group_cmd, "commands", {})
        for cmd_name, cmd in commands.items():
            self._extract_from_command(
                group_name, cmd_name, cmd, host_args, host_options
            )

    def _extract_from_command(
        self,
        group_name: str,
        cmd_name: str,
        cmd: click.Command,
        host_args: dict[str, dict[str, HostMatchMode]],
        host_options: dict[str, dict[str, list[str]]],
    ) -> None:
        """Extract host completion metadata from a single command."""
        if not hasattr(cmd, "callback") or not cmd.callback:
            return

        sig = inspect.signature(cmd.callback)
        for param in sig.parameters.values():
            self._extract_from_parameter(
                group_name, cmd_name, cmd, param, host_args, host_options
            )

    def _extract_from_parameter(
        self,
        group_name: str,
        cmd_name: str,
        cmd: click.Command,
        param: inspect.Parameter,
        host_args: dict[str, dict[str, HostMatchMode]],
        host_options: dict[str, dict[str, list[str]]],
    ) -> None:
        """Extract host metadata from a parameter annotation."""
        if param.annotation == inspect.Parameter.empty:
            return

        if get_origin(param.annotation) is not Annotated:
            return

        args = get_args(param.annotation)
        for metadata in args[1:]:
            if isinstance(metadata, HostArgument):
                if group_name not in host_args:
                    host_args[group_name] = {}
                mode = (
                    HostMatchMode.MULTIPLE
                    if metadata.multiple
                    else HostMatchMode.SINGLE
                )
                host_args[group_name][cmd_name] = mode

            elif isinstance(metadata, HostOption):
                option_names = self._get_option_names_from_param(cmd, param.name)
                if option_names:
                    if group_name not in host_options:
                        host_options[group_name] = {}
                    host_options[group_name][cmd_name] = option_names

    def _get_option_names_from_param(
        self, cmd: click.Command, param_name: str
    ) -> list[str]:
        """Extract option names from Click command param."""
        for click_param in getattr(cmd, "params", []):
            if getattr(click_param, "name", None) == param_name:
                return getattr(click_param, "opts", [])
        return []

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

    def _complete_help_command(self, words: list[str], text: str) -> list[Completion]:
        """Complete the 'help' builtin command with available commands."""
        if not self.root_command:
            return []

        main_commands = getattr(self.root_command, "commands", {})
        current = "" if text.endswith(" ") else (words[1] if len(words) > 1 else "")
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

    def _complete_host_names(
        self, current: str, sp: int, exclude: set[str] | None = None
    ) -> list[Completion]:
        """
        Return host name completions

        Optionally exclude already-used host names during completion.
        """
        host_names = self._get_host_names()
        exclude = exclude or set()
        matching = [h for h in host_names if h.startswith(current) and h not in exclude]

        return self._make_completions(matching, sp)

    def _complete_host_positional_arg(
        self, command: str, words: list[str], text: str, current: str, sp: int
    ) -> Generator[Completion, None, None]:
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

        mode = subcmd_config[words[1]]

        # Determine if this position accepts host names based on completion mode
        accepts_hosts = False
        match mode:
            case HostMatchMode.SINGLE:
                # Only position 0
                accepts_hosts = arg_position == 0
            case HostMatchMode.MULTIPLE:
                # Any position
                accepts_hosts = True

        if accepts_hosts:
            # For single-host commands, no exclusion needed
            exclude = set()
            if mode == HostMatchMode.MULTIPLE:
                # Multi-host command: exclude hosts already specified
                exclude = set(non_opt_args)
                if not text.endswith(" ") and non_opt_args:
                    # Remove the current partial word from exclusions
                    exclude.discard(non_opt_args[-1])

            yield from self._complete_host_names(current, sp, exclude=exclude)

    def _is_flag_option(self, subsub: click.Command, option_name: str) -> bool:
        """
        Check if an option is a flag (doesn't take a value).

        This is used to determine whether or not to halt completion after
        an option is completed.
        """
        if not hasattr(subsub, "params"):
            return False

        # We check for Click/Typer is_flag, count, and BOOL type
        # All of them imply the option value is the option itself (a flag)
        # We have to do this due to inconsistencies across Typer/Click details.
        for param in subsub.params:
            if option_name in getattr(param, "opts", []):
                if getattr(param, "is_flag", False):
                    return True
                if getattr(param, "count", False):
                    return True
                param_type = getattr(param, "type", None)
                if param_type and getattr(param_type, "name", None) == "BOOL":
                    return True

        return False

    def _complete_subsubcommand(
        self, command: str, subcommand, words: list[str], text: str, used_opts: set
    ) -> Generator[Completion, None, None]:
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
            for param in getattr(subsub, "params", []):
                opts.update(o for o in getattr(param, "opts", []) if o.startswith("--"))

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

    def get_completions(
        self, document: Document, complete_event
    ) -> Generator[Completion, None, None]:
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
                yield from self._complete_help_command(words, text)
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
        commands = getattr(subcommand, "commands", {})
        if commands:
            if len(words) == 1 or (len(words) == 2 and not text.endswith(" ")):
                matching = [name for name in commands if name.startswith(current)]

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

    def __init__(self, ctx: Context, prompt_text: str = "exosphere> ") -> None:
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

    def _setup_history(self) -> History:
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
        if not self.root_command:
            self.console.print("[red]No root command available[/red]")
            return

        if not args:
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

        # In interactive mode, unhide all commands.
        # This ensures interactive-only commands are visible.
        self._unhide_commands(subcommand)

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

    def _unhide_commands(self, command: click.Command) -> None:
        """
        Recursively unhide all subcommands for interactive mode.

        In interactive mode, we want to show all commands including those
        marked as hidden (which are typically interactive-only commands).

        :param command: The command to unhide along with its subcommands
        """
        # Unhide the command itself if it has a hidden attribute
        if hasattr(command, "hidden"):
            command.hidden = False

        # Unhide all subcommands recursively
        for subcmd in getattr(command, "commands", {}).values():
            self._unhide_commands(subcmd)

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
        Hidden commands will be included.
        """
        if self.root_command:
            subcommands = getattr(self.root_command, "commands", {})
            lines = []
            for name, cmd in subcommands.items():
                help_text = getattr(cmd, "help", None) or "No description available."

                # Show only the first line of the help text for brevity
                # This can be a multi-line string
                first_line = help_text.split("\n")[0]

                lines.append(f"[cyan]{name:<13}[/cyan] {first_line}")

            if lines:
                content = "\n".join(lines)
                panel = Panel.fit(
                    content,
                    title="Commands",
                    title_align="left",
                    border_style="dim",
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
