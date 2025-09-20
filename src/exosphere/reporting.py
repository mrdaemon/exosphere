"""
Reporting module

This module provides functionality to render reports in various formats
using Jinja2 templates.
"""

from datetime import datetime
from typing import Any

import jinja2

from exosphere import __version__
from exosphere.objects import Host


class ReportRenderer:
    """
    Renders reports in various formats using Jinja2 templates.

    The core of the reporting system, handles setup of the Jinja2
    environment, loading templates, and rendering them with
    provided data.
    """

    def __init__(self):
        self.env = self.setup_jinja_environment()

    def setup_jinja_environment(self) -> jinja2.Environment:
        """
        Setup Jinja2 environment with templates from the package.

        Configures autoescaping, global functions, and custom filters.

        :return: Configured Jinja2 Environment
        """
        # Use PackageLoader instead of FileSystemLoader for installed packages
        loader = jinja2.PackageLoader("exosphere")
        env = jinja2.Environment(
            loader=loader, autoescape=jinja2.select_autoescape(["html", "htm", "xml"])
        )

        # Add utility functions to the global context
        env.globals["now"] = lambda: datetime.now().astimezone()
        env.globals["exosphere_version"] = __version__

        # Add custom filters for table formatting
        env.filters["ljust"] = lambda s, width: str(s).ljust(width)
        env.filters["rjust"] = lambda s, width: str(s).rjust(width)
        env.filters["center"] = lambda s, width: str(s).center(width)

        return env

    def render_markdown(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as Markdown."""
        template = self.env.get_template("report.md.j2")
        return template.render(hosts=hosts, **kwargs)

    def render_text(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as plain text."""
        template = self.env.get_template("report.txt.j2")
        return template.render(hosts=hosts, **kwargs)

    def render_html(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as HTML."""
        template = self.env.get_template("report.html.j2")
        return template.render(hosts=hosts, **kwargs)
