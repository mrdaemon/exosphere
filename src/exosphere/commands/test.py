import typer

app = typer.Typer(
    help="Test Commands",
    no_args_is_help=True,
)


@app.command()
def greet(name: str = "World") -> None:
    """Greet the user."""
    typer.echo(f"Hello, {name}!")


@app.command()
def beep() -> None:
    """Beep."""
    typer.echo("Beep!")
