"""
UI command module
"""

import logging

import typer
from rich.console import Console

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


@app.command()
def webstart() -> None:
    """Start the Exosphere Web UI."""
    logger = logging.getLogger(__name__)

    try:
        from textual_serve.server import Server
    except ImportError:
        console = Console(stderr=True)
        logger.error("Web UI component is not installed.")
        console.print(
            "The Exosphere Web UI component is not installed. "
            r"Please install 'exosphere-cli\[web]' to use this feature."
        )
        raise typer.Exit(code=1)
    else:
        logger.info("Starting Exosphere Web UI Server")
        server = Server(command="exosphere ui start")
        server.serve()
