"""
REPL module for Exosphere

This module implements the Exosphere REPL, providing enhanced features
like command history, autocompletion, and better line editing while
maintaining Rich output formatting.
"""

import logging
import shlex
from collections.abc import Callable, Iterable, Iterator
from typing import get_args

from cyclopts import App, ArgumentCollection, CycloptsError
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, History
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.panel import Panel

from exosphere import app_config
from exosphere import context as app_context
from exosphere.objects import Host

logger = logging.getLogger(__name__)

# Common help flags, will be stripped before resolving a command chain
_HELP_FLAGS = {"--help"}

# Builtin (REPL-only) commands, mostly for help.
BUILTINS = {
    "exit": "Exit the interactive shell",
    "quit": "Exit the interactive shell",
    "clear": "Clear the console",
}


def _accepts_host(argument) -> bool:
    """
    Check if argument resolves host names.

    Host arguments and options are typed with the Host converter, so we
    check if their hint involves :class:`Host`, either directly, or as a
    tuple for variadics.
    """
    stack = [getattr(argument, "hint", None)]
    while stack:
        current = stack.pop()
        if current is Host:
            return True
        stack.extend(get_args(current))
    return False


def _subcommands(app: App) -> list[str]:
    """Real subcommand names of an app (no leading-dash flags)."""
    return [name for name in app if not name.startswith("-")]


class ExosphereCompleter(Completer):
    """
    Readline-like completion for Exosphere commands

    Handles completion of top-level commands, subcommands, their options
    and choice values, host-name arguments/options, as well as the
    builtin REPL commands (e.g. 'help', 'exit', etc).
    """

    def __init__(self, app: App, host_names: Callable[[], list[str]]) -> None:
        self.app = app
        self.host_names = host_names

        # Cache ArgumentCollection for performance
        # It is invariant once the app tree is built, so we can cache
        # it per command node instead of re-introspecting every keystroke
        self._ac_cache: dict[int, ArgumentCollection] = {}

    def _argument_collection(self, node: App) -> ArgumentCollection:
        """
        Returns the argument collection for a command node.
        Caches the result for performance.
        """
        key = id(node)

        if key not in self._ac_cache:
            self._ac_cache[key] = node.assemble_argument_collection()

        return self._ac_cache[key]

    def _complete(self, matches: Iterable[str], prefix: str) -> Iterator[Completion]:
        """
        Yield completions for matches with the given prefix.

        We append a space on full match for rapid tab-through completion,
        an ancestral behavior from Quality Things like Bash that I, for
        one, absolutely expect. A time tried tradition.
        """
        candidates = sorted(m for m in set(matches) if m.startswith(prefix))
        startpos = -len(prefix)

        if len(candidates) == 1:
            yield Completion(candidates[0] + " ", start_position=startpos)
            return

        for match in candidates:
            yield Completion(match, start_position=startpos)

    def _host_matches(
        self, prefix: str, exclude: set[str] | None = None
    ) -> Iterator[Completion]:
        """
        Yield host-name completions

        Optionally excludes hosts in the given set, which is useful for
        hosts that have already been consumed/completed in the current
        command line.
        """
        exclude = exclude or set()
        hosts = [h for h in self.host_names() if h not in exclude]
        yield from self._complete(hosts, prefix)

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterator[Completion]:
        """
        Retrieve completion based on current input

        Provides the main completer logic for Exosphere commands.

        :param document: The current input document
        :param complete_event: The completion event (not used here)
        """
        text = document.text_before_cursor
        words = text.split()
        ends_space = text == "" or text.endswith(" ")
        current = "" if ends_space else (words[-1] if words else "")
        settled = words if ends_space else words[:-1]

        # Complete top-level commands and builtins
        if not settled:
            yield from self._complete(_subcommands(self.app) + list(BUILTINS), current)
            return

        head = settled[0]

        # Handle built-in commands
        # Only 'help' completes commands, others take no arguments
        if head in ("exit", "quit", "clear"):
            return
        if head == "help":
            if len(settled) == 1:
                yield from self._complete(_subcommands(self.app), current)
            return

        # Resolve the command chain
        _chain, apps, unused = self.app.parse_commands(settled)
        node = apps[-1]

        # Complete group subcommands
        subs = _subcommands(node)
        if subs and not unused:
            yield from self._complete(subs, current)
            return

        # Introspect command arguments for leaf commands
        # (hits cache, if available, for performance)
        try:
            ac = self._argument_collection(node)
        except Exception:  # noqa: BLE001
            return

        used_opts = {token for token in unused if token.startswith("-")}

        # Completing an option name.
        if current.startswith("-"):
            opts = ["--help"]
            for arg in ac:
                # We only complete long options, for discoverability
                opts.extend(name for name in arg.names if name.startswith("--"))
            yield from self._complete(
                (opt for opt in opts if opt not in used_opts), current
            )
            return

        # Complete option values for last option, if applicable
        prev = unused[-1] if unused else ""
        if prev.startswith("-"):
            for arg in ac:
                if prev in arg.names:
                    choices = arg.get_choices()
                    if choices:
                        yield from self._complete(list(choices), current)
                        return
                    if _accepts_host(arg):
                        yield from self._host_matches(current)
                        return
                    if not arg.is_flag():
                        # Nothing to offer here
                        return
                    break

        # Complete positional host arguments
        # Stop after a single positional host, unless it's variadic
        # (e.g. *hosts), then keep handing out more until we run out
        positional_host = next(
            (
                arg
                for arg in ac
                if _accepts_host(arg)
                and not any(name.startswith("-") for name in arg.names)
            ),
            None,
        )

        if positional_host is not None:
            used_hosts = {token for token in unused if not token.startswith("-")}
            if positional_host.is_var_positional() or not used_hosts:
                yield from self._host_matches(current, exclude=used_hosts)


class ExosphereREPL:
    """
    REPL component for Exosphere

    Provides an interactive interface with enhanced features:
    - Command history with search (Ctrl+R)
    - Fun Expected Keybinds Handling (ctrl+d, ctrl+c etc)
    - Tab autocompletion down to subcommand, option and values
    - Cross-platform compatibility (not relying on readline)
    - Rich formatted output
    - Unified handling of commands from a root command
    - Built-in commands for console management and help
    - And probably more, as I start to regret my life choices.
    """

    def __init__(self, app: App, prompt_text: str = "exosphere> ") -> None:
        """
        Initialize the REPL with the given app and prompt.


        :param app: Cyclopts App object instance
        :param prompt_text: The prompt string to display.
        """
        self.app = app
        self.prompt_text = prompt_text
        self.console = Console()
        self.builtins = BUILTINS

        # Reveal interactive-only (hidden) commands
        # We keep these hidden from normal CLI help since they only
        # make sense across multiple commands (e.g. 'connections')
        _unhide(app)

        # Setup persistent history
        self.history = self._setup_history()

        # Setup the specialized completer
        self.completer = ExosphereCompleter(app, self._host_names)

    def _host_names(self) -> list[str]:
        """Host names from the current inventory (for completion)."""
        if app_context.inventory is None:
            return []
        return [host.name for host in app_context.inventory.hosts]

    def _setup_history(self) -> History:
        """
        Setup persistent command history using FileHistory.

        The history file will be dumped in the State directory for
        Exosphere, according to platform conventions.

        Falls back to in-memory history if the file cannot be opened.
        """
        try:
            history_file = app_config["options"]["history_file"]
            return FileHistory(str(history_file))
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not setup persistent history: %s", e)
            logger.warning("REPL is falling back to in-memory history")

            from prompt_toolkit.history import InMemoryHistory

            return InMemoryHistory()

    def cmdloop(self, intro: str | None = None) -> None:
        """
        Main REPL loop

        Read, Eval, Print, Lather, Rinse, Repeat.
        """

        # Standard optional intro/banner subtext
        if intro:
            self.console.print(intro)
            self.console.print()

        # Use HTML to format the prompt since it's what prompt_toolkit
        # expects. I would use Rich tags here, but this is a different
        # animal entirely, with its own syntax and coffee bar.
        prompt_html = HTML(f"<ansiblue>{self.prompt_text}</ansiblue>")

        while True:
            try:
                # Prompt for user input with colored prompt
                # We use readline-style completion for familiarity
                user_input = prompt(
                    prompt_html,
                    history=self.history,
                    completer=self.completer,
                    complete_while_typing=False,
                    enable_history_search=True,
                    complete_style=CompleteStyle.READLINE_LIKE,
                )

                # Skip over empty input
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
            except Exception as e:  # noqa: BLE001
                # Catch-all for unexpected crashes
                self.console.print(f"[red]Unexpected error in REPL: {e}[/red]")
                logger.exception("Unexpected error in REPL")

    def execute_command(self, line: str) -> None:
        """
        Parse and Execute a command with Rich output formatting
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

            # Execute application commands
            self._execute_command(args)

        except ValueError as e:
            self.console.print(f"[red]Error parsing command: {e}[/red]")
        except EOFError:
            # Re-raise EOFError so it reaches the main loop
            # Allows Ctrl+D to exit gracefully
            raise
        except Exception as e:  # noqa: BLE001
            self.console.print(f"[red]Error executing command: {e}[/red]")
            logger.exception("Error executing command: %s", line)

    def _execute_command(self, args: list[str]) -> None:
        """
        Dispatch and Execute an Application command

        We route "--help" to scoped help explicitly to avoid full
        command name resolution, essentially stripping the root command
        from usage lines.

        Otherwise, we run via the Cyclopts token handling, which
        cleanly delegates parsing and exit codes to the library.

        Command exit codes are swallowed in interactive mode, since the
        standard output/error text is the intended feedback.
        Cyclopts and general parse errors are surfaced, however.
        """
        head = args[0]

        # Route --help through scoped help handler
        # Rewrites command names to be relative
        if any(token in _HELP_FLAGS for token in args):
            if self._scoped_help(args):
                return

            # Fall back to normal dispatch if scoped help couldn't
            # handle it (e.g. unrecognized command)
            args = [token for token in args if token not in _HELP_FLAGS]
            if not args:
                return
            head = args[0]

        # Bare groups (sub-app that has subcommands but has no further
        # tokens, and has no default command) also get routed to scoped
        # help, for the same reason,
        _chain, apps, unused = self.app.parse_commands(args)
        node = apps[-1]
        if _subcommands(node) and not unused and node.default_command is None:
            self._scoped_help(args)
            return

        try:
            self.app(
                args,
                exit_on_error=False,
                print_error=True,  # Use native CycloptsPanel for errors
                result_action="return_value",
            )
        except SystemExit:
            # Handle sys.exit calls from commands gracefully, without
            # exiting the REPL - output is already handled by now.
            pass
        except CycloptsError:
            # Handle CycloptsErrors gracefully
            # It already prints the errors
            pass
        except Exception as e:
            # Something went horribly wrong and we have no idea what
            self.console.print(f"[red]Error executing {head}: {e}[/red]")
            logger.exception("Error executing command '%s'", head)

    def _scoped_help(self, args: list[str]) -> bool:
        """
        Render help for the typed command, with relative command name

        This allows help given from interactive mode to omit the root
        command for usage lines, which is much friendlier in context.

        Example: "exosphere sudo generate" --> "sudo generate"

        Returns False when the tokens leave an unrecognized command, so the
        caller can fall back to normal dispatch (surfacing the proper
        unknown-command error rather than the root help).
        """
        tokens = [token for token in args if token not in _HELP_FLAGS]
        chain, apps, unused = self.app.parse_commands(tokens)

        # If there are leftover tokens that don't look like options or their
        # values, don't try to twiddle help any further.
        # NOTE: misfires for a group whose default command takes a positional
        # (none do today, but noting for the future).
        if _subcommands(apps[-1]) and unused and not unused[0].startswith("-"):
            return False

        if len(apps) >= 2:
            apps[1].help_print(list(chain[1:]))
        else:
            self.app.help_print([])

        return True

    def _show_help(self, args: list[str]) -> None:
        """
        Show help with Rich formatting
        """
        if not args:
            # General help
            self._show_general_help()
        elif args[0] in self.builtins:
            # Handle built-in commands
            self.console.print(f"[cyan]Built-in: {self.builtins[args[0]]}[/cyan]")
        elif args[0] in ("--help", "help"):
            # Show help for help, because someone is bound to try
            # Might as well leave a small easter egg for them.
            self.console.print(
                "[cyan]Yes, that is indeed how that works.[/cyan]\n"
                "Use 'help' without arguments for general help."
            )
        else:
            # Specific command help, delegate to scoped help. If the command
            # isn't recognized, dispatch it normally so Cyclopts reports the
            # unknown command (and suggestions) rather than rendering nothing.
            if not self._scoped_help([args[0], "--help"]):
                self._execute_command([args[0]])

    def _show_general_help(self) -> None:
        """
        Show general help for interactive mode
        Hidden commands will be included.
        """
        lines = []
        for name in _subcommands(self.app):
            sub = self.app[name]
            help_text = (sub.help or "").strip() or "No description available."

            # Show only the first line of the help text for brevity
            # This can be a multi-line string
            first_line = help_text.split("\n")[0]

            lines.append(f"[cyan]{name:<13}[/cyan] {first_line}")

        if lines:
            panel = Panel.fit(
                "\n".join(lines),
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

        self.console.print(
            f"[dim]Built-in commands: {', '.join(self.builtins.keys())}[/dim]"
        )


def _unhide(app: App) -> None:
    """
    Recursively reveal hidden commands/sub-apps for interactive use.

    Interactive-only commands (e.g. ``connections``, ``inventory save``) are
    registered with "show=False" to stay out of the normal CLI help.
    In interactive mode (the REPL), we want them visible, so we
    recursively flip that back to True.

    Since this is done at runtime, it never leaks to a CLI invocation.
    """
    for name in list(app):
        if name.startswith("-"):
            continue

        sub = app[name]

        try:
            sub.show = True
        except Exception:  # noqa: BLE001
            pass

        _unhide(sub)


def start_repl(app: App, prompt_text: str = "exosphere> ") -> None:
    """
    Start the Exosphere REPL.

    :param app: Cyclopts application.
    :param prompt_text: The prompt string to display
    """
    repl = ExosphereREPL(app, prompt_text)
    intro = (
        "[cyan]Welcome to the Exosphere interactive shell[/cyan]\n"
        "Type 'help' for commands or 'ui start' to start the UI."
    )
    repl.cmdloop(intro=intro)
