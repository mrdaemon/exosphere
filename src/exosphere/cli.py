import logging

import typer
from click_shell import make_click_shell
from rich.console import Console

from exosphere import __version__
from exosphere.commands import host, inventory, ui

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

app = typer.Typer(
    no_args_is_help=False,
)

# Setup commands from modules
app.add_typer(inventory.app, name="inventory")
app.add_typer(ui.app, name="ui")
app.add_typer(host.app, name="host")


# The default command fall through call back
# We use this to start the REPL if no command is given.
@app.callback(invoke_without_command=True)
def cli(ctx: typer.Context) -> None:
    """
    Exosphere CLI
    """
    if ctx.invoked_subcommand is None:
        logger = logging.getLogger(__name__)
        logger.info("Starting Exosphere REPL interface")

        # Print the banner
        console = Console()
        console.print(banner)

        # Start interactive REPL
        repl = make_click_shell(
            ctx,
            prompt="exosphere> ",
        )
        repl.cmdloop()
        typer.Exit(0)
