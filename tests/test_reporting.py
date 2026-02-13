"""
Tests for the reporting module.
"""

import json
from datetime import datetime, timezone

import jinja2
import jsonschema
import pytest

from exosphere.data import Update
from exosphere.objects import Host
from exosphere.reporting import ReportRenderer, ReportScope, ReportType
from exosphere.schema import get_host_report_schema


class TestReportRenderer:
    """Tests for the ReportRenderer class."""

    @pytest.fixture
    def renderer(self):
        """Create a ReportRenderer instance for testing."""
        return ReportRenderer()

    @pytest.fixture
    def sample_host(self):
        """Create a sample Host object with updates for testing."""
        host = Host(
            name="test-host",
            ip="192.168.1.100",
            description="Test server for unit tests",
        )
        host.os = "linux"
        host.flavor = "ubuntu"
        host.version = "22.04"
        host.package_manager = "apt"
        host.last_refresh = datetime.now(tz=timezone.utc)
        host.supported = True

        # Add some test updates
        host.updates = [
            Update(
                name="curl",
                current_version="7.81.0-1ubuntu1.4",
                new_version="7.81.0-1ubuntu1.6",
                security=True,
                source="security",
            ),
            Update(
                name="vim",
                current_version="2:8.2.3458-2ubuntu2.2",
                new_version="2:8.2.3458-2ubuntu2.4",
                security=False,
                source="updates",
            ),
        ]

        return host

    @pytest.fixture
    def empty_host(self):
        """Create a Host object without updates for testing."""
        host = Host(
            name="empty-host",
            ip="192.168.1.101",
        )
        host.os = "linux"
        host.package_manager = "apt"
        host.last_refresh = None  # Never refreshed
        host.updates = []

        return host

    @pytest.fixture
    def stale_host(self):
        """Create a Host object with stale data for testing."""
        from datetime import timedelta

        host = Host(
            name="stale-host",
            ip="192.168.1.102",
            description="Host with stale data",
        )
        host.os = "linux"
        host.flavor = "ubuntu"
        host.version = "22.04"
        host.package_manager = "apt"
        # Set last_refresh to 25 hours ago (past default 24h stale threshold)
        host.last_refresh = datetime.now(tz=timezone.utc) - timedelta(hours=25)
        host.supported = True
        host.updates = [
            Update(
                name="test-package",
                current_version="1.0.0",
                new_version="1.0.1",
                security=False,
                source="main",
            ),
        ]

        return host

    def test_renderer_initialization(self, renderer):
        """Test that ReportRenderer initializes correctly."""
        assert isinstance(renderer.env, jinja2.Environment)
        assert isinstance(renderer.text_env, jinja2.Environment)

        # Test that environments have expected configurations
        assert renderer.env.trim_blocks is False
        assert renderer.env.lstrip_blocks is False
        assert renderer.text_env.trim_blocks is True
        assert renderer.text_env.lstrip_blocks is True

    @pytest.mark.parametrize(
        "text_mode,expected_trim,expected_lstrip",
        [
            (True, True, True),  # Text environment with whitespace control
            (False, False, False),  # Generic environment without whitespace control
        ],
        ids=["text", "generic"],
    )
    def test_setup_jinja_environment(
        self, renderer, text_mode, expected_trim, expected_lstrip
    ):
        """Test Jinja2 environment setup for both text and HTML environments."""
        env = renderer.setup_jinja_environment(text=text_mode)

        # Test whitespace control settings
        assert env.trim_blocks is expected_trim
        assert env.lstrip_blocks is expected_lstrip

        # Global functions should be in the environment
        assert "now" in env.globals
        assert "exosphere_version" in env.globals

        # And so should custom filters
        assert "ljust" in env.filters
        assert "rjust" in env.filters
        assert "center" in env.filters

    def test_render_json(self, renderer, sample_host, empty_host, stale_host):
        """Test JSON rendering."""
        hosts = [sample_host, empty_host, stale_host]
        result = renderer.render_json(hosts, ReportType.full)

        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 3

        # Check structure of first host
        host_data = parsed[0]
        assert host_data["name"] == "test-host"
        assert host_data["ip"] == "192.168.1.100"
        assert host_data["description"] == "Test server for unit tests"
        assert len(host_data["updates"]) == 2
        assert "stale" in host_data
        assert isinstance(host_data["stale"], bool)
        assert host_data["stale"] is False

        # Check security updates count
        security_updates = [u for u in host_data["updates"] if u["security"]]
        assert len(security_updates) == 1
        assert security_updates[0]["name"] == "curl"

        # Check structure of empty host
        empty_host_data = parsed[1]
        assert empty_host_data["name"] == "empty-host"
        assert empty_host_data["ip"] == "192.168.1.101"
        assert "stale" in empty_host_data
        assert isinstance(empty_host_data["stale"], bool)

        # Empty host should have no updates
        assert empty_host_data["updates"] == []

        # Check structure of stale host
        stale_host_data = parsed[2]
        assert stale_host_data["name"] == "stale-host"
        assert stale_host_data["stale"] is True

        # Ensure third host is marked as stale
        assert parsed[2]["name"] == "stale-host"
        assert parsed[2]["stale"] is True

    def test_render_text(self, renderer, sample_host):
        """Test text rendering."""
        hosts = [sample_host]
        result = renderer.render_text(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should contain expected content
        assert "SYSTEM UPDATES REPORT" in result
        assert "test-host (192.168.1.100)" in result
        assert "Test server for unit tests" in result
        assert "linux ubuntu 22.04" in result
        assert "apt" in result
        assert "Updates (2):" in result
        assert "Security Updates (1):" in result
        assert "curl:" in result
        assert "vim:" in result

    def test_render_markdown(self, renderer, sample_host):
        """Test Markdown rendering."""
        hosts = [sample_host]
        result = renderer.render_markdown(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        assert "# System Updates Report" in result
        assert "## test-host (192.168.1.100)" in result
        assert "**Description**: Test server for unit tests" in result
        assert "**OS**: linux ubuntu 22.04" in result
        assert "**Package Manager**: apt" in result
        assert "| Package | Current Version | New Version | Sec | Source |" in result
        assert "curl" in result
        assert "vim" in result

    def test_render_html(self, renderer, sample_host):
        """Test HTML rendering."""
        hosts = [sample_host]
        result = renderer.render_html(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should be valid HTML5 document
        assert "<!DOCTYPE html>" in result
        assert '<html lang="en">' in result
        assert "</html>" in result

        # Should contain proper meta information
        assert '<meta charset="UTF-8">' in result
        assert '<meta name="generator" content="Exosphere' in result
        assert "<title>System Updates Report -" in result

        # Should have CSS styling
        assert "<style>" in result
        assert "font-family:" in result
        assert ".security" in result

        # Should contain main content structure
        assert "<h1>System Updates Report</h1>" in result
        assert '<div class="summary">' in result
        assert "<strong>Selected hosts:</strong> 1" in result
        assert "<strong>Security updates:</strong> 1" in result

        # Should contain host information
        assert "<h2>test-host (192.168.1.100)</h2>" in result
        assert (
            '<div class="host-description">Test server for unit tests</div>' in result
        )
        assert "<strong>OS:</strong> linux ubuntu 22.04" in result
        assert "<strong>Package Manager:</strong> apt" in result

        # Should contain updates table
        assert "<h3>Available Updates (2)</h3>" in result
        assert "<thead>" in result
        assert "<th>Package</th>" in result
        assert "<th>Security</th>" in result
        assert "<tbody>" in result

        # Should contain update data
        assert "<strong>curl</strong>" in result
        assert "<strong>vim</strong>" in result
        assert "7.81.0-1ubuntu1.4" in result
        assert "7.81.0-1ubuntu1.6" in result
        assert '<span class="security">Yes</span>' in result  # Security update marked

        # Should have proper footer
        assert "<footer>" in result
        assert (
            'Generated with <a href="https://github.com/mrdaemon/exosphere">Exosphere</a>'
            in result
        )

    @pytest.mark.parametrize(
        "hosts_fixture,hosts_count,expected_checks",
        [
            (
                "empty_list",
                0,
                {
                    "json": lambda result: json.loads(result) == [],
                    "text": lambda result: "Selected hosts: 0" in result,
                    "markdown": lambda result: "**Selected hosts:** 0" in result,
                    "html": lambda result: "<html" in result,
                },
            ),
            (
                "empty_host",
                1,
                {
                    "json": lambda result: json.loads(result)[0]["updates"] == [],
                    "text": lambda result: "No updates available." in result,
                    "markdown": lambda result: "**No updates available.**" in result,
                    "html": lambda result: (
                        "<em>No updates available.</em>" in result
                        and "<strong>Total updates:</strong> 0" in result
                    ),
                },
            ),
        ],
        ids=["empty_hosts_list", "host_without_updates"],
    )
    def test_render_edge_cases(
        self, renderer, empty_host, hosts_fixture, hosts_count, expected_checks
    ):
        """
        Test rendering edge cases: empty list and host without updates.

        Those should be handled by calling code, but the renderer itself should
        still handle them reasonably gracefully.
        """
        hosts = [] if hosts_fixture == "empty_list" else [empty_host]

        # Test JSON, because as always, it's a special boy
        json_result = renderer.render_json(hosts, ReportType.full)
        assert expected_checks["json"](json_result)

        # Test template-based formats
        for format_name in ["text", "markdown", "html"]:
            render_method = getattr(renderer, f"render_{format_name}")
            result = render_method(
                hosts,
                hosts_count=hosts_count,
                report_type=ReportType.full,
                report_scope=ReportScope.filtered,
            )
            assert expected_checks[format_name](result)

    def test_render_html_with_navigation(self, renderer, sample_host, empty_host):
        """Test HTML rendering with navigation enabled (default)"""
        hosts = [sample_host, empty_host]
        result = renderer.render_html(
            hosts,
            hosts_count=2,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should contain table of contents
        assert '<div class="toc">' in result
        assert "<h3>Quick Navigation</h3>" in result
        assert 'href="#host-0"' in result
        assert 'href="#host-1"' in result
        assert (
            '<span class="update-count">(2)</span>' in result
        )  # sample_host has 2 updates
        assert (
            '<span class="update-count">(0)</span>' in result
        )  # empty_host has 0 updates

        # Should have proper anchor IDs
        assert 'id="host-0"' in result
        assert 'id="host-1"' in result

    def test_render_html_without_navigation(self, renderer, sample_host):
        """Test HTML rendering with navigation disabled"""
        hosts = [sample_host]
        result = renderer.render_html(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
            navigation=False,
        )

        # Should NOT contain table of contents HTML elements
        assert '<div class="toc">' not in result
        assert "<h3>Quick Navigation</h3>" not in result
        assert 'class="toc-link"' not in result

    def test_custom_filters(self, renderer):
        """Test custom Jinja2 filters."""
        # Test ljust filter
        ljust_result = renderer.text_env.filters["ljust"]("test", 10)
        assert ljust_result == "test      "

        # Test rjust filter
        rjust_result = renderer.text_env.filters["rjust"]("test", 10)
        assert rjust_result == "      test"

        # Test center filter
        center_result = renderer.text_env.filters["center"]("test", 10)
        assert center_result == "   test   "

    def test_global_functions(self, renderer):
        """Test global functions available in templates."""
        # Test now() function returns current time
        now_func = renderer.text_env.globals["now"]
        result = now_func()
        assert isinstance(result, datetime)

        # Test exosphere_version is available
        version = renderer.text_env.globals["exosphere_version"]
        assert isinstance(version, str)
        assert len(version) > 0

    def test_render_json_security_only(self, renderer, sample_host, empty_host):
        """Test JSON rendering with security_only flag."""
        hosts = [sample_host, empty_host]

        # Test security_only=True
        result = renderer.render_json(hosts, ReportType.security_only)
        parsed = json.loads(result)

        # Should be valid JSON with same structure
        assert isinstance(parsed, list)
        assert len(parsed) == 2

        # First host should have only security updates in updates field
        host_data = parsed[0]
        assert host_data["name"] == "test-host"
        assert "updates" in host_data
        assert len(host_data["updates"]) == 1  # Only security updates
        assert host_data["updates"][0]["name"] == "curl"
        assert host_data["updates"][0]["security"] is True

        # Second host should still have empty updates
        # It generally gets filtered out by the CLI but this is still
        # the expected behavior otherwise.
        assert len(parsed[1]["updates"]) == 0

    @pytest.mark.parametrize("format_name", ["text", "markdown", "html"])
    def test_render_security_only_templates(self, renderer, sample_host, format_name):
        """Test security_only flag across template-based formats."""
        hosts = [sample_host]

        # Get the appropriate render method
        render_method = getattr(renderer, f"render_{format_name}")
        result = render_method(
            hosts,
            hosts_count=1,
            report_type=ReportType.security_only,
            report_scope=ReportScope.filtered,
        )

        # All formats should show security-only summary statistics
        if format_name == "text":
            assert "Hosts with security updates: 1" in result
            assert "Total security updates: 1" in result
            assert "Security Updates (1):" in result

            assert "Total hosts:" not in result
            assert "Total updates:" not in result
        elif format_name == "markdown":
            assert "**Hosts with security updates:** 1" in result
            assert "**Total security updates:** 1" in result

            assert "**Total hosts:**" not in result
            assert "**Total updates:**" not in result
        elif format_name == "html":
            assert "<strong>Hosts with security updates:</strong> 1" in result
            assert "<strong>Total security updates:</strong> 1" in result

            assert "<strong>Total hosts:</strong>" not in result
            assert "<strong>Total updates:</strong>" not in result
            assert "<h3>Available Updates (1)</h3>" in result

        # Only security updates
        assert "curl" in result
        assert "vim" not in result

    def test_render_text_stale_indicator(self, renderer, stale_host):
        """Test that stale hosts show a stale indicator in text output."""
        hosts = [stale_host]
        result = renderer.render_text(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should contain stale indicator
        assert "stale-host" in result
        assert "Stale" in result or "stale" in result

    def test_render_markdown_stale_indicator(self, renderer, stale_host):
        """Test that stale hosts show a stale indicator in markdown output."""
        hosts = [stale_host]
        result = renderer.render_markdown(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should contain stale indicator
        assert "stale-host" in result
        assert "Stale" in result or "stale" in result

    def test_render_html_stale_indicator(self, renderer, stale_host):
        """Test that stale hosts show a stale indicator in HTML output."""
        hosts = [stale_host]
        result = renderer.render_html(
            hosts,
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
        )

        # Should contain stale indicator (with CSS class)
        assert "stale-host" in result
        assert "stale" in result.lower()


class TestJSONSchemaValidation:
    """Tests for JSON schema validation of report output."""

    @pytest.fixture
    def renderer(self):
        return ReportRenderer()

    @pytest.fixture
    def sample_hosts(self):
        # Host with full data
        host1 = Host(
            name="complete-host",
            ip="127.1.1.10",
            description="Host with complete data",
        )
        host1.os = "linux"
        host1.flavor = "ubuntu"
        host1.version = "22.04"
        host1.package_manager = "apt"
        host1.last_refresh = datetime.now(tz=timezone.utc)
        host1.supported = True
        host1.online = True
        host1.updates = [
            Update(
                name="curl",
                current_version="7.81.0-1ubuntu1.4",
                new_version="7.81.0-1ubuntu1.6",
                security=True,
                source="security",
            ),
            Update(
                name="new-package",
                current_version=None,  # New install - no current version
                new_version="1.0.0",
                security=False,
                source="main",
            ),
        ]

        # Host with minimal/undiscovered data
        # Description field is expected to be elided
        host2 = Host(name="minimal-host", ip="127.1.1.20")
        host2.os = None
        host2.flavor = None
        host2.version = None
        host2.package_manager = None
        host2.last_refresh = None
        host2.supported = True
        host2.online = False
        host2.updates = []

        return [host1, host2]

    @pytest.mark.parametrize(
        "report_type",
        [ReportType.full, ReportType.updates_only, ReportType.security_only],
    )
    def test_json_output_validates_against_schema(
        self, renderer, sample_hosts, report_type
    ):
        """Test that JSON output validates against our JSON schema."""
        json_output = renderer.render_json(sample_hosts, report_type)

        # Parse JSON and validate against schema
        data = json.loads(json_output)
        schema = get_host_report_schema()

        # This should not raise any exceptions
        jsonschema.validate(data, schema)

    def test_json_schema_empty_report(self, renderer):
        """Test that an empty report validates against the schema."""
        empty_json = renderer.render_json([], ReportType.full)
        data = json.loads(empty_json)
        schema = get_host_report_schema()

        # This should not raise any exceptions
        jsonschema.validate(data, schema)

        # Should be an empty array
        assert data == []

    def test_json_schema_optional_fields(self, renderer):
        """
        Test schema validation with optional fields

        Optional fields should be elided when empty/None
        and present when populated.
        """
        schema = get_host_report_schema()

        host_with_desc = Host("test1", "1.1.1.1", description="Test host")
        host_with_desc.last_refresh = datetime.now(tz=timezone.utc)

        host_without_desc = Host("test2", "2.2.2.2")  # No description
        host_without_desc.last_refresh = datetime.now(tz=timezone.utc)

        json_output = renderer.render_json(
            [host_with_desc, host_without_desc], ReportType.full
        )
        data = json.loads(json_output)
        jsonschema.validate(data, schema)

        assert "description" in data[0]
        assert "description" not in data[1]
