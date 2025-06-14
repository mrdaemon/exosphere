import logging
import sys
from typing import Annotated

# ------------------win32 readline monkeypatch---------------------
if sys.platform == "win32":
    try:
        # On windows, we use a wrapper module for pyreadline3 in order
        # to provide readline compatibility.
        from exosphere.compat import win32readline as readline

        # This needs monkeypatched in order for click_shell to make use
        # of it instead of its internal, broken, legacy pyreadline.
        sys.modules["readline"] = readline
    except ImportError:
        sys.stderr.write(
            "Warning: pyreadline3 not found. "
            "Interactive shell may not enable all features.\n"
        )
# -----------------------------------------------------------------

from click_shell import make_click_shell
from rich import print
from rich.panel import Panel
from typer import Argument, Context, Exit, Typer

from exosphere import __version__
from exosphere.commands import host, inventory

banner = f"""[turquoise4]
                         ▗▖
                         ▐▌
 ▟█▙ ▝█ █▘ ▟█▙ ▗▟██▖▐▙█▙ ▐▙██▖ ▟█▙  █▟█▌ ▟█▙
▐▙▄▟▌ ▐█▌ ▐▛ ▜▌▐▙▄▖▘▐▛ ▜▌▐▛ ▐▌▐▙▄▟▌ █▘  ▐▙▄▟▌
▐▛▀▀▘ ▗█▖ ▐▌ ▐▌ ▀▀█▖▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘ █   ▐▛▀▀▘
▝█▄▄▌ ▟▀▙ ▝█▄█▘▐▄▄▟▌▐█▄█▘▐▌ ▐▌▝█▄▄▌ █   ▝█▄▄▌
 ▝▀▀ ▝▀ ▀▘ ▝▀▘  ▀▀▀ ▐▌▀▘ ▝▘ ▝▘ ▝▀▀  ▀    ▝▀▀
                    ▐▌ [green]v{__version__}[/green][/turquoise4]
"""

app = Typer(
    no_args_is_help=False,
)

# Setup commands from modules
app.add_typer(inventory.app, name="inventory")
# app.add_typer(ui.app, name="ui") # Ui module disabled until release
app.add_typer(host.app, name="host")


# Help wrapper to use typer's help system
# Except for the root command, which has its own implementation
@app.command(hidden=True)
def help(ctx: Context, command: Annotated[str | None, Argument()] = None):
    msg = "\nUse '<command> --help' or 'help <command>' for help on a specific command."
    # Show root help if no command is specified
    if not command:
        if ctx.parent and getattr(ctx.parent, "command", None):
            subcommands = getattr(ctx.parent.command, "commands", {})
            lines = []
            for name, cmd in subcommands.items():
                if cmd.hidden:
                    continue
                lines.append(
                    f"[cyan]{name:<11}[/cyan] {cmd.help or 'No description available.'}"
                )
            content = "\n".join(lines)
            panel = Panel.fit(
                content,
                title="Commands",
                title_align="left",
            )
            print("\nAvailable modules during interactive use:\n")
            print(panel)
        print(msg)
        return

    # Show command help if one is specified
    subcommand = None
    if ctx.parent and getattr(ctx.parent, "command", None):
        subcommands = getattr(ctx.parent.command, "commands", None)
        subcommand = subcommands.get(command) if subcommands else None
        if subcommand:
            subcommand.get_help(ctx)
            print(f"\nUse '{str(subcommand.name)} <command> --help' for more details.")
            return

    # Fall through for unknown commands
    print(f"[red]Unkown command '{command}'[/red]")
    print(msg)


# The default command fall through call back
# We use this to start the REPL if no command is given.
@app.callback(invoke_without_command=True)
def cli(ctx: Context) -> None:
    """
    Exosphere CLI
    """
    if ctx.invoked_subcommand is None:
        logger = logging.getLogger(__name__)
        logger.info("Starting Exosphere REPL interface")

        # Print the banner
        print(banner)

        # Start interactive REPL
        repl = make_click_shell(
            ctx,
            prompt="exosphere> ",
        )
        repl.cmdloop()
        Exit(0)
