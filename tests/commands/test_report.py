"""
Tests for the report command module.
"""

import pytest
import typer
from typer.testing import CliRunner

from exosphere.commands.report import generate
from exosphere.data import Update
from exosphere.objects import Host
from exosphere.reporting import ReportScope, ReportType

runner = CliRunner(env={"NO_COLOR": "1"})

# There's either a bug in Typer or I'm misunderstanding something
# fundamentally, but since report contains a single subcommand,
# running runner.invoke(app, ["generate", ...]) results in
# parsing fuckery where free arguments contain "generate" and other
# strange stuff, making tests absurdly brittle.
#
# We work around it here by making the generate command available
# at the root level and pretend the issue doesn't exist.
generate_app = typer.Typer()
generate_app.command()(generate)


@pytest.fixture
def mock_renderer(mocker):
    """Mock ReportRenderer and return mock methods that return test data."""
    mock_renderer_class = mocker.patch(
        "exosphere.commands.report.ReportRenderer", autospec=True
    )
    mock_instance = mock_renderer_class.return_value

    # Configure return values for each render method
    mock_instance.render_json.return_value = "[]"
    mock_instance.render_text.return_value = "Mock text report"
    mock_instance.render_markdown.return_value = "# Mock markdown report"
    mock_instance.render_html.return_value = "<html>Mock html report</html>"

    return mock_instance


@pytest.fixture
def sample_host():
    """Create a sample Host object with updates for testing."""
    host = Host(name="test-host", ip="192.168.1.100")
    host.os = "linux"
    host.flavor = "ubuntu"
    host.version = "22.04"
    host.package_manager = "apt"
    host.supported = True  # Required for filtering

    # Add test updates
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
def empty_host():
    """Create a Host object without updates for testing."""
    host = Host(name="empty-host", ip="192.168.1.101")
    host.os = "linux"
    host.package_manager = "apt"
    host.supported = True  # Required for filtering
    host.updates = []

    return host


@pytest.fixture
def unsupported_host():
    """Create a Host object that is not supported for testing."""
    host = Host(name="unsupported", ip="192.168.1.100")
    host.supported = False
    host.package_manager = None
    return host


@pytest.fixture
def mock_get_hosts(mocker):
    """Fixture that returns a patcher function for get_hosts_or_error."""

    def _patch_hosts(hosts):
        return mocker.patch(
            "exosphere.commands.report.get_hosts_or_error", return_value=hosts
        )

    return _patch_hosts


class TestGenerateCommand:
    """Tests for the report generate command with parametrized tests to reduce duplication."""

    @pytest.mark.parametrize(
        "format_name,expected_method,expected_output",
        [
            ("json", "render_json", "[]"),
            ("text", "render_text", "Mock text report"),
            ("markdown", "render_markdown", "# Mock markdown report"),
            ("html", "render_html", "<html>Mock html report</html>"),
        ],
        ids=["json", "text", "markdown", "html"],
    )
    def test_generate_basic_formats(
        self,
        mock_get_hosts,
        mock_renderer,
        sample_host,
        format_name,
        expected_method,
        expected_output,
    ):
        """
        Test basic report generation for all formats.
        """
        mock_get_hosts([sample_host])

        result = runner.invoke(generate_app, ["--format", format_name])
        assert result.exit_code == 0

        # Verify the correct renderer method was called
        render_method = getattr(mock_renderer, expected_method)
        render_method.assert_called_once_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.complete,
            navigation=True,
        )

        # Verify output contains expected content
        assert expected_output in result.stdout

    @pytest.mark.parametrize(
        "navigation_flag,expected_navigation",
        [
            ([], True),
            (["--no-navigation"], False),
        ],
        ids=["navigation", "no_navigation"],
    )
    def test_generate_html_navigation_option(
        self,
        mock_get_hosts,
        mock_renderer,
        sample_host,
        navigation_flag,
        expected_navigation,
    ):
        """
        Test HTML generation with navigation options
        """
        mock_get_hosts([sample_host])

        args = ["--format", "html"] + navigation_flag
        result = runner.invoke(generate_app, args)
        assert result.exit_code == 0

        mock_renderer.render_html.assert_called_once_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.complete,
            navigation=expected_navigation,
        )

    @pytest.mark.parametrize(
        "flag",
        ["--updates-only", "-u"],
        ids=["long_flag", "short_flag"],
    )
    def test_generate_with_updates_only_filter(
        self, mock_get_hosts, mock_renderer, sample_host, empty_host, flag
    ):
        """
        Test --updates-only filter logic (both long and short flags)
        """
        mock_get_hosts([sample_host, empty_host])

        result = runner.invoke(generate_app, ["--format", "json", flag])
        assert result.exit_code == 0

        mock_renderer.render_json.assert_called_once()
        call_args = mock_renderer.render_json.call_args[0]
        passed_hosts = call_args[0]

        assert len(passed_hosts) == 1
        assert passed_hosts[0].name == "test-host"

    def test_generate_with_specific_hosts_filtered_scope(
        self, mock_get_hosts, mock_renderer, sample_host, empty_host
    ):
        """
        Test that specifying hosts on command line results in ReportScope.filtered
        """
        mock_get_hosts([sample_host])

        result = runner.invoke(generate_app, ["--format", "json", "test-host"])
        assert result.exit_code == 0

        mock_renderer.render_json.assert_called_once_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
            navigation=True,
        )

    @pytest.mark.parametrize(
        "hosts,expected_exit_code",
        [
            ("unsupported_hosts", 1),
            (None, 1),
        ],
        ids=["no_supported_hosts", "host_lookup_failure"],
    )
    def test_generate_error_cases(
        self, mock_get_hosts, unsupported_host, hosts, expected_exit_code
    ):
        """
        Test error handling for various failure scenarios

        In practice, get_hosts_or_error will handle displaying error messages.
        Since we mock get_hosts_or_error to return None for error cases,
        no specific error messages are generated by the command itself.

        We only verify that the command exits with the expected code.
        """
        if hosts == "unsupported_hosts":
            hosts_data = [unsupported_host]
        else:
            hosts_data = hosts

        # For unsupported hosts, get_hosts_or_error should return None
        if hosts == "unsupported_hosts":
            mock_get_hosts(None)  # Simulate no supported hosts
        else:
            mock_get_hosts(hosts_data)

        result = runner.invoke(generate_app, ["--format", "json"])
        assert result.exit_code == expected_exit_code

    @pytest.mark.parametrize(
        "quiet_flag,expect_message",
        [
            (
                False,
                True,
            ),
            (True, False),
        ],
        ids=["no_quiet", "quiet"],
    )
    def test_updates_only_with_no_matching_hosts(
        self, mock_get_hosts, mock_renderer, empty_host, quiet_flag, expect_message
    ):
        """
        Test --updates-only behavior when no hosts have updates
        """
        mock_get_hosts([empty_host])
        mock_renderer.render_json.return_value = "[]"

        args = ["--format", "json", "--updates-only"]
        if quiet_flag:
            args.append("--quiet")

        result = runner.invoke(generate_app, args)
        assert result.exit_code == 0

        if expect_message:
            assert "No hosts with available updates found" in result.stderr
        else:
            assert result.stderr == ""
            assert result.stdout.strip() == "[]"  # Empty JSON array rendered

    @pytest.mark.parametrize(
        "flag",
        ["--security-updates-only", "-s"],
        ids=["long_flag", "short_flag"],
    )
    def test_security_updates_only_flag(
        self, mock_get_hosts, mock_renderer, sample_host, flag
    ):
        """Test that --security-updates-only flag (both long and short) is passed to renderer methods."""
        mock_get_hosts([sample_host])

        result = runner.invoke(generate_app, ["--format", "json", flag])

        assert result.exit_code == 0
        mock_renderer.render_json.assert_called_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.security_only,
            report_scope=ReportScope.complete,
            navigation=True,
        )

    def test_security_updates_only_filters_hosts(
        self, mock_get_hosts, mock_renderer, empty_host
    ):
        """Test that hosts without security updates are filtered out."""
        mock_get_hosts([empty_host])

        result = runner.invoke(
            generate_app, ["--format", "json", "--security-updates-only"]
        )

        assert result.exit_code == 0
        assert "No hosts with security updates found" in result.stderr

    @pytest.mark.parametrize(
        "use_tee,expect_stdout",
        [
            (False, False),
            (True, True),
        ],
        ids=["no_tee", "with_tee"],
    )
    def test_file_output_with_tee_behavior(
        self,
        mock_get_hosts,
        mock_renderer,
        sample_host,
        tmp_path,
        use_tee,
        expect_stdout,
    ):
        """
        Test file output, with and without --tee flag
        """
        mock_get_hosts([sample_host])
        mock_renderer.render_json.return_value = '{"test": "data"}'

        output_file = tmp_path / "report.json"
        args = ["--format", "json", "--output", str(output_file)]
        if use_tee:
            args.append("--tee")

        result = runner.invoke(generate_app, args)
        assert result.exit_code == 0

        assert output_file.exists()
        assert output_file.read_text() == '{"test": "data"}'

        if expect_stdout:
            # Rich formats JSON with indentation, so check for key content
            assert '"test"' in result.stdout and '"data"' in result.stdout
        else:
            assert result.stdout == ""

    @pytest.mark.parametrize(
        "quiet_flag,expect_message",
        [
            (False, True),
            (True, False),
        ],
        ids=["no_quiet", "quiet"],
    )
    def test_quiet_flag_with_file_output(
        self,
        mock_get_hosts,
        mock_renderer,
        sample_host,
        tmp_path,
        quiet_flag,
        expect_message,
    ):
        """
        Test file write out with and without --quiet flag
        """
        mock_get_hosts([sample_host])
        mock_renderer.render_text.return_value = "test output"

        output_file = tmp_path / "test_output.txt"
        args = ["--format", "text", "--output", str(output_file)]
        if quiet_flag:
            args.append("--quiet")

        result = runner.invoke(generate_app, args)

        assert result.exit_code == 0
        assert result.stdout == ""  # No stdout when using --output
        assert output_file.read_text() == "test output"

        if expect_message:
            assert "Report of type" in result.stderr and "saved to" in result.stderr
        else:
            assert (
                "Report of type" not in result.stderr
                and "saved to" not in result.stderr
            )

    def test_file_output_error_handling(self, mock_get_hosts, sample_host, tmp_path):
        """
        Test file write error handling

        This is supremely basic but it really has the same result
        with any sort of Exception.
        """
        mock_get_hosts([sample_host])

        # Test file write error with invalid path
        invalid_path = tmp_path / "nonexistent" / "directory" / "file.json"
        result = runner.invoke(
            generate_app, ["--format", "json", "--output", str(invalid_path)]
        )

        assert result.exit_code == 1
        assert "Failed to write to" in result.stderr
