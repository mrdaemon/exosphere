"""
UI command module
"""

import logging

from cyclopts import App

from exosphere.ui.app import ExosphereUi

ROOT_HELP = """
Start the Exosphere User Interface

Launches the Text-based User Interface (TUI). When started from
interactive mode, quitting the UI returns you to the prompt.

Takes no arguments; the 'start' subcommand is an alias kept for
backward compatibility with older versions of Exosphere.
"""

app = App(name="ui", help=ROOT_HELP, help_flags=["--help"])


@app.default
def run_tui() -> None:
    """
    Start the Exosphere Text-based User Interface (TUI)

    This is the entry point for the 'ui' command.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting Exosphere UI")

    ui_app = ExosphereUi()
    ui_app.run()


@app.command
def start() -> None:
    """
    Start the UI (compatibility alias)

    This subcommand is kept for backwards compatibility with older
    versions of Exosphere, to preserve the muscle memory of users who
    have relied on it since 1.0.0. It simply launches the UI, exactly
    like invoking 'ui' with no arguments.
    """
    run_tui()
