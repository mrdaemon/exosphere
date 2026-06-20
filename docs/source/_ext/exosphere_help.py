"""
Sphinx extension to render an SVG screenshot of Exosphere CLI help output

Provides a Sphinx directive that renders the Cyclopts --help screen as
an inline SVG, as a magic, dynamic, regenerates-on-build "screenshot".

This is another entry in the "what am I doing with my life?" category
of Sphinx extensions within Exosphere, but it does restore the help
preview functionality that sphinxcontrib-typer provided previously.

It mainly works through Rich's Console being able to output SVG with
theming and window chrome, which we then embed in the page. It uses
a StringIO capture, remaining cross-platform and in-memory.

The previous Typer-centric extension had a bit more options to
customize the way that renders, but this is good enough for us.

Could this be made generic and public? Maybe, but I don't want to
maintain it outside of Exosphere. It's also shockingly trivial.

Usage::

    .. exosphere-help:: exosphere.cli:app
       :title: exosphere --help

    .. exosphere-help:: exosphere.cli:app
       :command: inventory
       :title: exosphere inventory --help

Options:

``title``
    Title shown in the rendered terminal window. Defaults to
    "exosphere --help".
``command``
    Space-separated command path for sub-command help (e.g.
    "inventory"). Defaults to root app help.
``width``
    Console width in columns. Defaults to ``90``.
``theme``
    A rich.terminal_theme name (e.g. "MONOKAI", "NIGHT_OWLISH").
    Defaults to "DIMMED_MONOKAI", which looks good generally.
"""

import importlib
import io

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from rich import terminal_theme
from rich.console import Console

# Default to Dimmed Monokai which is the sanest oob choice
_DEFAULT_THEME = "DIMMED_MONOKAI"


def _resolve_app(target: str):
    """Resolve a ``module:attr`` (or ``module``) target to a Cyclopts App."""
    module_name, _, attr = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr or "app")


class ExosphereHelpDirective(Directive):
    """Render a Cyclopts app's ``--help`` output as an inline SVG."""

    required_arguments = 1  # "module:attr", e.g. exosphere.cli:app
    optional_arguments = 0
    has_content = False
    option_spec = {
        "title": directives.unchanged,
        "command": directives.unchanged,  # tokens for sub-command help
        "width": directives.positive_int,
        "theme": directives.unchanged,
    }

    def _error(self, message: str):
        return [self.state_machine.reporter.error(message, line=self.lineno)]

    def run(self):
        target = self.arguments[0]

        try:
            app = _resolve_app(target)
        except Exception as exc:  # noqa: BLE001
            return self._error(
                f"exosphere-help: cannot load app from {target!r}: {exc}"
            )

        command = self.options.get("command", "").split() or None
        title = self.options.get("title") or "exosphere --help"
        width = self.options.get("width", 90)

        theme_name = self.options.get("theme", _DEFAULT_THEME)
        theme = getattr(terminal_theme, theme_name, None)

        if theme is None:
            return self._error(f"exosphere-help: unknown theme {theme_name!r}")

        recorder = Console(record=True, width=width, file=io.StringIO())
        try:
            app.help_print(command, console=recorder)
        except Exception as exc:  # noqa: BLE001
            return self._error(
                f"exosphere-help: failed to render help for {target!r}: {exc}"
            )

        svg = recorder.export_svg(title=title, theme=theme)
        return [nodes.raw("", svg, format="html")]


def setup(app):
    app.add_directive("exosphere-help", ExosphereHelpDirective)

    print("[INFO] Exosphere Help Screen Renderer extension loaded")

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
