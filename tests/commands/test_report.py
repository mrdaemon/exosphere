"""
Tests for the report command module.
"""

import pytest
from typer.testing import CliRunner

from exosphere.commands.report import app
from exosphere.data import Update
from exosphere.objects import Host

runner = CliRunner(env={"NO_COLOR": "1"})


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

        result = runner.invoke(app, ["generate", "--format", format_name])
        assert result.exit_code == 0

        # Verify the correct renderer method was called
        render_method = getattr(mock_renderer, expected_method)
        render_method.assert_called_once_with(
            [sample_host], navigation=True, security_only=False
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

        args = ["generate", "--format", "html"] + navigation_flag
        result = runner.invoke(app, args)
        assert result.exit_code == 0

        mock_renderer.render_html.assert_called_once_with(
            [sample_host], navigation=expected_navigation, security_only=False
        )

    def test_generate_with_updates_only_filter(
        self, mock_get_hosts, mock_renderer, sample_host, empty_host
    ):
        """
        Test --updates-only filter logic
        """
        mock_get_hosts([sample_host, empty_host])

        result = runner.invoke(app, ["generate", "--format", "json", "--updates-only"])
        assert result.exit_code == 0

        mock_renderer.render_json.assert_called_once()
        call_args = mock_renderer.render_json.call_args[0]
        passed_hosts = call_args[0]

        assert len(passed_hosts) == 1
        assert passed_hosts[0].name == "test-host"

    @pytest.mark.parametrize(
        "hosts,expected_error_message",
        [
            ("unsupported_hosts", "Host(s) found but none can be used!"),
            (None, None),
        ],
        ids=["no_supported_hosts", "host_lookup_failure"],
    )
    def test_generate_error_cases(
        self, mock_get_hosts, unsupported_host, hosts, expected_error_message
    ):
        """
        Test error handling for various failure scenarios
        """
        if hosts == "unsupported_hosts":
            hosts_data = [unsupported_host]
        else:
            hosts_data = hosts

        mock_get_hosts(hosts_data)

        result = runner.invoke(app, ["generate", "--format", "json"])
        assert result.exit_code == 1

        if expected_error_message:
            assert expected_error_message in result.stderr

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

        args = ["generate", "--format", "json", "--updates-only"]
        if quiet_flag:
            args.append("--quiet")

        result = runner.invoke(app, args)
        assert result.exit_code == 0

        if expect_message:
            assert "No hosts with available updates found" in result.stderr
        else:
            assert result.stderr == ""
            assert result.stdout.strip() == "[]"  # Empty JSON array rendered

    def test_security_updates_only_flag(
        self, mock_get_hosts, mock_renderer, sample_host
    ):
        """Test that --security-updates-only flag is passed to renderer methods."""
        mock_get_hosts([sample_host])

        result = runner.invoke(
            app, ["generate", "--format", "json", "--security-updates-only"]
        )

        assert result.exit_code == 0
        mock_renderer.render_json.assert_called_with(
            [sample_host], navigation=True, security_only=True
        )

    def test_security_updates_only_short_flag(
        self, mock_get_hosts, mock_renderer, sample_host
    ):
        """Test that -s short flag works for --security-updates-only."""
        mock_get_hosts([sample_host])

        result = runner.invoke(app, ["generate", "--format", "json", "-s"])

        assert result.exit_code == 0
        mock_renderer.render_json.assert_called_with(
            [sample_host], navigation=True, security_only=True
        )

    def test_security_updates_only_filters_hosts(
        self, mock_get_hosts, mock_renderer, empty_host
    ):
        """Test that hosts without security updates are filtered out."""
        mock_get_hosts([empty_host])

        result = runner.invoke(
            app, ["generate", "--format", "json", "--security-updates-only"]
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
        args = ["generate", "--format", "json", "--output", str(output_file)]
        if use_tee:
            args.append("--tee")

        result = runner.invoke(app, args)
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
        args = ["generate", "--format", "text", "--output", str(output_file)]
        if quiet_flag:
            args.append("--quiet")

        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert result.stdout == ""  # No stdout when using --output
        assert output_file.read_text() == "test output"

        if expect_message:
            assert "Report saved to" in result.stderr
        else:
            assert "Report saved to" not in result.stderr

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
            app, ["generate", "--format", "json", "--output", str(invalid_path)]
        )

        assert result.exit_code == 1
        assert "Failed to write to" in result.stderr
