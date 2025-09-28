#!/usr/bin/env python3
"""
Example Reports Generation Script

Utilitarian script to generate example reports with fake host data,
mostly intended to be used for documentation and example purposes.

This should be ran via the poe task `docs-mkreports` whenever
the templates or reporting code is changed, to keep the examples
up to date.

Note: If you're venturing in there, please be aware that this is a poor
representation of how the Exosphere API is meant to function, and only
cobbled together to serve a specific purpose.

This is also fairly brittle and profound API changes in the reporting
module will result in changes needing to be made here as well.

I'm sorry.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from exosphere.data import Update
from exosphere.objects import Host
from exosphere.reporting import ReportRenderer, ReportScope, ReportType


def create_sample_hosts() -> list[Host]:
    """
    Create a set of realistic sample hosts for reporting examples.
    Everything is made up, but kept reasonably plausible.

    We just kind of kitbash class members with values, never really
    setting them through the intended methods, for simplicity.
    """
    hosts: list[Host] = []

    # Web server with security updates
    web_server = Host(name="web-prod-01", ip="10.0.1.10", description="Web Server")
    web_server.os = "linux"
    web_server.flavor = "ubuntu"
    web_server.version = "22.04"
    web_server.package_manager = "apt"
    web_server.supported = True
    web_server.online = True
    web_server.last_refresh = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    web_server.updates = [
        Update("apache2", "2.4.52-1ubuntu4.6", "2.4.52-1ubuntu4.7", True, "security"),
        Update("php8.1", "8.1.2-1ubuntu2.13", "8.1.2-1ubuntu2.14", True, "security"),
        Update("curl", "7.81.0-1ubuntu1.10", "7.81.0-1ubuntu1.13", False, "updates"),
        Update(
            "vim", "2:8.2.3458-2ubuntu2.2", "2:8.2.3458-2ubuntu2.4", False, "updates"
        ),
    ]
    hosts.append(web_server)

    # Database server with mixed updates
    db_server = Host(
        name="db-01", ip="10.0.2.20", description="PostgreSQL database server"
    )
    db_server.os = "linux"
    db_server.flavor = "debian"
    db_server.version = "12"
    db_server.package_manager = "apt"
    db_server.supported = True
    db_server.online = True
    db_server.last_refresh = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    db_server.updates = [
        Update("postgresql-14", "14.9-0+deb12u1", "14.10-0+deb12u1", True, "security"),
        Update("openssl", "3.0.9-1+deb12u3", "3.0.11-1+deb12u2", True, "security"),
        Update("rsync", "3.2.7-1", "3.2.7-1+deb12u1", False, "main"),
        Update("libextra3", None, "3.2.2-2", False, "main"),  # New dependency
    ]
    hosts.append(db_server)

    # Admin Server - just updates
    admin_server = Host(name="admin-01", ip="10.0.2.30", description="Admin Server")
    admin_server.os = "freebsd"
    admin_server.flavor = "freebsd"
    admin_server.version = "14.3-RELEASE-p3"
    admin_server.package_manager = "pkg"
    admin_server.supported = True
    admin_server.online = True
    admin_server.last_refresh = datetime.now(tz=timezone.utc) - timedelta(hours=3)
    admin_server.updates = [
        Update("en-freebsd-doc", "20250814,1", "20250920,1", False, "FreeBSD"),
        Update("expat", "2.7.1", "2.7.2", False, "FreeBSD"),
    ]
    hosts.append(admin_server)

    # Load balancer - up to date
    lb_server = Host(name="lb-01", ip="10.0.1.5", description="HAProxy load balancer")
    lb_server.os = "linux"
    lb_server.flavor = "rhel"
    lb_server.version = "9"
    lb_server.package_manager = "dnf"
    lb_server.supported = True
    lb_server.online = True
    lb_server.last_refresh = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    lb_server.updates = []  # No updates available
    hosts.append(lb_server)

    # Development server - offline and stale
    dev_server = Host(
        name="dev-staging",
        ip="10.0.3.100",
        description="Development and staging environment",
    )
    dev_server.os = "linux"
    dev_server.flavor = "ubuntu"
    dev_server.version = "20.04"
    dev_server.package_manager = "apt"
    dev_server.supported = True
    dev_server.online = False  # Currently offline
    dev_server.last_refresh = datetime.now(tz=timezone.utc) - timedelta(days=3)
    dev_server.updates = [
        # Has some cached updates from last time it was online
        Update("git", "1:2.34.1-1ubuntu1.9", "1:2.34.1-1ubuntu1.10", False, "updates"),
    ]
    hosts.append(dev_server)

    return hosts


def generate_example_reports() -> None:
    """Generate example reports in all formats."""
    hosts = create_sample_hosts()
    renderer = ReportRenderer()

    # Create output directory
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "examples" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate reports, mostly emulating supported CLI options

    print("Generating full reports (all hosts, all updates)...")
    _generate_report_set(
        renderer=renderer,
        output_dir=output_dir,
        prefix="full",
        hosts=hosts,
        hosts_count=len(hosts),
        report_type=ReportType.full,
        report_scope=ReportScope.complete,
    )

    print("Generating filtered reports (specific hosts selected)...")
    filtered_hosts = [hosts[0], hosts[1]]  # web-prod-01 and db-primary
    _generate_report_set(
        renderer=renderer,
        output_dir=output_dir,
        prefix="filtered",
        hosts=filtered_hosts,
        hosts_count=len(hosts),
        report_type=ReportType.full,
        report_scope=ReportScope.filtered,
    )

    print("Generating full-no-navigation report (HTML only)...")
    _generate_single_report(
        renderer=renderer,
        output_file=output_dir / "full-no-navigation.html",
        hosts=hosts,
        hosts_count=len(hosts),
        report_type=ReportType.full,
        report_scope=ReportScope.complete,
        format_type="html",
        navigation=False,
    )

    print("Generating security-only reports...")
    _generate_report_set(
        renderer=renderer,
        output_dir=output_dir,
        prefix="securityonly",
        hosts=hosts,
        hosts_count=len(hosts),
        report_type=ReportType.security_only,
        report_scope=ReportScope.complete,
    )

    print("Generating updates-only reports...")
    hosts_with_updates = [h for h in hosts if h.updates]
    _generate_report_set(
        renderer=renderer,
        output_dir=output_dir,
        prefix="updatesonly",
        hosts=hosts_with_updates,
        hosts_count=len(hosts),
        report_type=ReportType.updates_only,
        report_scope=ReportScope.complete,
    )

    print(f"\nExample reports generated in: {output_dir.relative_to(project_root)}")
    print(f"Total hosts: {len(hosts)}")


def _generate_report_set(
    renderer: ReportRenderer,
    output_dir: Path,
    prefix: str,
    hosts: list[Host],
    hosts_count: int,
    report_type: ReportType,
    report_scope: ReportScope,
) -> None:
    """Generate a set of reports in all formats."""
    formats = ["json", "txt", "md", "html"]

    for fmt in formats:
        output_file = output_dir / f"{prefix}.{fmt}"
        _generate_single_report(
            renderer=renderer,
            output_file=output_file,
            hosts=hosts,
            hosts_count=hosts_count,
            report_type=report_type,
            report_scope=report_scope,
            format_type=fmt,
        )


def _generate_single_report(
    renderer: ReportRenderer,
    output_file: Path,
    hosts: list[Host],
    hosts_count: int,
    report_type: ReportType,
    report_scope: ReportScope,
    format_type: str,
    **kwargs: Any,
) -> None:
    """Generate a single report file in the specified format."""

    render_methods = {
        "json": lambda: renderer.render_json(hosts, report_type),
        "txt": lambda: renderer.render_text(
            hosts, hosts_count, report_type, report_scope, **kwargs
        ),
        "md": lambda: renderer.render_markdown(
            hosts, hosts_count, report_type, report_scope, **kwargs
        ),
        "html": lambda: renderer.render_html(
            hosts, hosts_count, report_type, report_scope, **kwargs
        ),
    }

    render_method = render_methods.get(format_type)
    if render_method is None:
        raise ValueError(f"Unsupported format: {format_type}")

    content = render_method()
    output_file.write_text(content, encoding="utf-8")
    print(f"  -> {output_file.name}")


if __name__ == "__main__":
    generate_example_reports()
