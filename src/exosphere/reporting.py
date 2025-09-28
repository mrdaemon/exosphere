"""
Reporting module

This module provides functionality to render reports in various formats
using Jinja2 templates.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import jinja2

from exosphere import __version__
from exosphere.objects import Host

logger: logging.Logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Available report types"""

    full = "Full Report"
    updates_only = "Updates Only Report"
    security_only = "Security Only Report"


class ReportScope(str, Enum):
    """Scope of the report"""

    complete = "complete"  # All hosts in inventory
    filtered = "filtered"  # Subset of hosts


class OutputFormat(str, Enum):
    """Available output formats for reports"""

    text = "text"
    html = "html"
    markdown = "markdown"
    json = "json"


class ReportRenderer:
    """
    Renders reports in various formats using Jinja2 templates.

    The core of the reporting system, handles setup of the Jinja2
    environment, loading templates, and rendering them with
    provided data.
    """

    def __init__(self):
        """Initialize the report renderer."""

        self.env = self.setup_jinja_environment(text=False)
        self.text_env = self.setup_jinja_environment(text=True)

    def setup_jinja_environment(self, text: bool) -> jinja2.Environment:
        """
        Setup Jinja2 environment with templates from the package.

        Configures autoescaping, global functions, and custom filters.

        :param text: Turns on trim_blocks and lstrip_blocks for text templates
        :return: Configured Jinja2 Environment
        """
        logger.debug("Setting up reporting environment")

        # Setup loader using PackageLoader for the module's namespace
        # This implies templates can be found under the "templates" directory
        loader = jinja2.PackageLoader("exosphere")
        env = jinja2.Environment(
            loader=loader,
            autoescape=jinja2.select_autoescape(["html", "htm", "xml"]),
            trim_blocks=text,
            lstrip_blocks=text,
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

    def render_markdown(
        self,
        hosts: list[Host],
        hosts_count: int,
        report_type: ReportType,
        report_scope: ReportScope,
        **kwargs: Any,
    ) -> str:
        """
        Render hosts data report as Markdown.

        :param hosts: List of Host objects to include in the report
        :param hosts_count: Total number of hosts selected for the report
        :param report_scope: Scope of the report (complete or filtered)
        :param report_type: Type of report (full, updates only, security only)
        :param kwargs: Additional context variables for the template
        :return: Rendered Markdown template string
        """

        logger.debug(
            "Rendering hosts data as Markdown with report_scope=%s, report_type=%s, kwargs: %s",
            report_scope,
            report_type,
            kwargs,
        )
        template = self.text_env.get_template("report.md.j2")
        return template.render(
            hosts=hosts,
            hosts_count=hosts_count,
            report_type=report_type,
            report_scope=report_scope,
            **kwargs,
        )

    def render_text(
        self,
        hosts: list[Host],
        hosts_count: int,
        report_type: ReportType,
        report_scope: ReportScope,
        **kwargs: Any,
    ) -> str:
        """
        Render hosts data report as plain text.

        :param hosts: List of Host objects to include in the report
        :param hosts_count: Total number of hosts selected for the report
        :param report_scope: Scope of the report (complete or filtered)
        :param report_type: Type of report (full, updates only, security only)
        :param kwargs: Additional context variables for the template
        :return: Rendered plain text template string
        """

        logger.debug(
            "Rendering hosts data as plain text with report_scope=%s, report_type=%s, kwargs: %s",
            report_scope,
            report_type,
            kwargs,
        )
        template = self.text_env.get_template("report.txt.j2")
        return template.render(
            hosts=hosts,
            hosts_count=hosts_count,
            report_type=report_type,
            report_scope=report_scope,
            **kwargs,
        )

    def render_html(
        self,
        hosts: list[Host],
        hosts_count: int,
        report_type: ReportType,
        report_scope: ReportScope,
        navigation: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Render hosts data report as HTML.

        :param hosts: List of Host objects to include in the report
        :param hosts_count: Total number of hosts selected for the report
        :param navigation: Whether to include the quick navigation section
        :param report_type: Type of report (full, updates only, security only)
        :param report_scope: Scope of the report (complete or filtered)
        :param kwargs: Additional context variables for the template
        :return: Rendered HTML template string
        """

        logger.debug(
            "Rendering hosts data as HTML with navigation=%s, report_type=%s, report_scope=%s, kwargs: %s",
            navigation,
            report_type,
            report_scope,
            kwargs,
        )
        template = self.env.get_template("report.html.j2")
        return template.render(
            hosts=hosts,
            hosts_count=hosts_count,
            report_type=report_type,
            navigation=navigation,
            report_scope=report_scope,
            **kwargs,
        )

    def render_json(
        self,
        hosts: list[Host],
        report_type: ReportType,
        **kwargs: Any,
    ) -> str:
        """
        Render hosts data report as JSON.

        Does not involve any template, simply uses json.dumps
        on Host.to_dict() under the hood for the informational properties

        Elides optional fields (like description) when empty/None for cleaner JSON.
        Discovery fields (os, flavor, etc.) are always present, null if undiscovered.

        kwargs are accepted for interface consistency but ignored.

        :param hosts: List of Host objects to include in the report
        :param report_type: Type of report (full, updates only, security only)
        :param kwargs: Additional context variables (not used in JSON rendering)
        :return: JSON string representation of the hosts data
        """

        logger.debug(
            "Rendering hosts data as JSON with report_type=%s, kwargs: %s",
            report_type,
            kwargs,
        )
        report_data = []
        for host in hosts:
            host_dict = host.to_dict()
            if report_type == ReportType.security_only:
                # Replace 'updates' with security updates only
                host_dict["updates"] = [
                    update.__dict__.copy() for update in host.security_updates
                ]

            # Elide optional user-provided fields when empty
            self._clean_optional_fields(host_dict)
            report_data.append(host_dict)

        return json.dumps(report_data, indent=2)

    def _clean_optional_fields(self, host_dict: dict) -> None:
        """
        Remove truly optional fields when they have no meaningful value.

        Keeps discovery fields (os, flavor, etc.) as null when undiscovered
        to maintain schema consistency, but removes user-optional fields
        like description when empty.

        Modifies the dictionary in-place.

        :param host_dict: Host dictionary to clean
        """
        # Remove optional user-provided fields when empty/None
        if not host_dict.get("description"):
            host_dict.pop("description", None)
