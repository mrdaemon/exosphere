"""
UI command module
"""

import logging

from cyclopts import App

from exosphere.commands.utils import err_console
from exosphere.ui.app import ExosphereUi

ROOT_HELP = """
Exosphere User Interface

Commands to start the Text-based or Web-based User Interface.
"""

app = App(name="ui", help=ROOT_HELP, help_flags=["--help"])


@app.command
def start() -> None:
    """Start the Exosphere UI."""
    logger = logging.getLogger(__name__)
    logger.info("Starting Exosphere UI")

    ui_app = ExosphereUi()
    ui_app.run()


@app.command
def webstart() -> int:
    """Start the Exosphere Web UI."""
    logger = logging.getLogger(__name__)

    try:
        from textual_serve.server import Server
    except ImportError:
        logger.error("Web UI component is not installed.")
        err_console.print(
            "The Exosphere Web UI component is not installed. "
            r"Please install 'exosphere-cli\[web]' to use this feature."
        )
        return 2  # Application error: component not installed
    else:
        logger.info("Starting Exosphere Web UI Server")
        server = Server(command="exosphere ui start")
        server.serve()

    return 0
