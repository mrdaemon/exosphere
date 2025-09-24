"""
Reporting module

This module provides functionality to render reports in various formats
using Jinja2 templates.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import jinja2

from exosphere import __version__
from exosphere.objects import Host

logger: logging.Logger = logging.getLogger(__name__)


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
        logger.debug("Setting up reporting environment")

        # Setup loader using PackageLoader for the module's namespace
        # This implies templates can be found under the "templates" directory
        loader = jinja2.PackageLoader("exosphere")
        env = jinja2.Environment(
            loader=loader, autoescape=jinja2.select_autoescape(["html", "htm", "xml"])
        )

        logger.debug("Setting up utility functions and filters for templates")

        # Add utility functions to the global context
        env.globals["now"] = lambda: datetime.now(tz=timezone.utc).astimezone()
        env.globals["exosphere_version"] = __version__

        # Add custom filters for table formatting
        env.filters["ljust"] = lambda s, width: str(s).ljust(width)
        env.filters["rjust"] = lambda s, width: str(s).rjust(width)
        env.filters["center"] = lambda s, width: str(s).center(width)

        return env

    def render_markdown(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as Markdown."""
        logger.debug("Rendering hosts data as Markdown")
        template = self.env.get_template("report.md.j2")
        return template.render(hosts=hosts, **kwargs)

    def render_text(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as plain text."""
        logger.debug("Rendering hosts data as plain text with kwargs: %s", kwargs)
        template = self.env.get_template("report.txt.j2")
        return template.render(hosts=hosts, **kwargs)

    def render_html(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as HTML."""
        logger.debug("Rendering hosts data as HTML with kwargs: %s", kwargs)
        template = self.env.get_template("report.html.j2")
        return template.render(hosts=hosts, **kwargs)

    def render_json(self, hosts: list[Host], **kwargs: Any) -> str:
        """Render hosts data as JSON."""
        logger.debug("Rendering hosts data as JSON with kwargs: %s", kwargs)
        report_data = [host.to_dict() for host in hosts]
        return json.dumps(report_data, indent=2)
