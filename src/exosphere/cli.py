import typer

from click_shell import make_click_shell

from exosphere import __version__
from exosphere.commands import test


banner = f"""
                         ▗▖
                         ▐▌
 ▟█▙ ▝█ █▘ ▟█▙ ▗▟██▖▐▙█▙ ▐▙██▖ ▟█▙  █▟█▌ ▟█▙
▐▙▄▟▌ ▐█▌ ▐▛ ▜▌▐▙▄▖▘▐▛ ▜▌▐▛ ▐▌▐▙▄▟▌ █▘  ▐▙▄▟▌
▐▛▀▀▘ ▗█▖ ▐▌ ▐▌ ▀▀█▖▐▌ ▐▌▐▌ ▐▌▐▛▀▀▘ █   ▐▛▀▀▘
▝█▄▄▌ ▟▀▙ ▝█▄█▘▐▄▄▟▌▐█▄█▘▐▌ ▐▌▝█▄▄▌ █   ▝█▄▄▌
 ▝▀▀ ▝▀ ▀▘ ▝▀▘  ▀▀▀ ▐▌▀▘ ▝▘ ▝▘ ▝▀▀  ▀    ▝▀▀
                    ▐▌

Exosphere CLI v{__version__}
"""

app = typer.Typer(
    no_args_is_help=False,
)

# Setup commands from modules
app.add_typer(test.app, name="test")


# The default command fall through call back
# We use this to start the REPL if no command is given.
@app.callback(invoke_without_command=True)
def cli(ctx: typer.Context) -> None:
    """
    Exosphere CLI
    """
    if ctx.invoked_subcommand is None:
        repl = make_click_shell(
            ctx,
            prompt="exosphere> ",
            intro=banner,
        )
        repl.cmdloop()
        typer.Exit(0)
