import click
import typer

from click_shell import make_click_shell

app = typer.Typer(
    no_args_is_help=False,
)

# click shell factory method


# A dumb test command to have something in the REPL
# and to see if it works as standalone cli as well
@app.command()
def greet(name: str = "World"):
    """Greet the user."""
    click.echo(f"Hello, {name}!")


# The default command fall through call back
# We use this to start the REPL if no command is given.
@app.callback(invoke_without_command=True)
def cli(ctx: typer.Context):
    """
    Exosphere CLI
    """
    if ctx.invoked_subcommand is None:
        repl = make_click_shell(
            ctx,
            prompt="exosphere> ",
            intro="Welcome to Exosphere v x.x",
        )
        repl.cmdloop()
        typer.Exit(0)
