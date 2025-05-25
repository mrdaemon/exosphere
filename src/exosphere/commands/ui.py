import logging

import typer

from exosphere.ui.app import ExosphereUi

app = typer.Typer(
    help="Exosphere UI",
    no_args_is_help=True,
)


@app.command()
def start() -> None:
    """Start the Exosphere UI."""
    logger = logging.getLogger(__name__)
    logger.info("Starting Exosphere UI")

    ui_app = ExosphereUi()
    ui_app.run()
