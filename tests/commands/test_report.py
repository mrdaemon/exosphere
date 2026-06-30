"""
Tests for the report command module.
"""

import json
from datetime import datetime, timezone

import pytest

from exosphere.commands import report
from exosphere.commands import utils as utils_module
from exosphere.data import Update
from exosphere.inventory import Inventory
from exosphere.objects import Host
from exosphere.reporting import ReportScope, ReportType
from exosphere.schema import get_host_report_schema


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Install deterministic consoles for the report command module."""
    patch_console(report)


@pytest.fixture(autouse=True)
def mock_inventory(mocker):
    """
    Patch context inventory for all tests.

    report.generate resolves a live inventory via get_inventory() and
    delegates update/security filtering to the real Inventory.filter_hosts,
    so we mirror this here.
    """
    fake_inventory = mocker.create_autospec(Inventory, instance=True)
    fake_inventory.hosts = []

    real = Inventory
    fake_inventory.filter_hosts.side_effect = lambda mode, hosts=None: (
        real.filter_hosts(fake_inventory, mode, hosts)
    )

    mocker.patch.object(utils_module.context, "inventory", fake_inventory)
    return fake_inventory


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
    """Fixture that returns a patcher function for get_hosts_or_all."""

    def _patch_hosts(hosts):
        return mocker.patch(
            "exosphere.commands.report.get_hosts_or_all", return_value=hosts
        )

    return _patch_hosts


def _status_host(
    name: str,
    updates: list[Update] | None = None,
    needs_reboot: bool | None = None,
    stale: bool = False,
    supported: bool = True,
) -> Host:
    """Build a Host with controlled state for status summary tests."""
    host = Host(name=name, ip="10.0.0.1")
    host.supported = supported
    host.os = "linux"
    host.package_manager = "apt"
    host.updates = updates or []
    host.needs_reboot = needs_reboot

    host.last_refresh = None if stale else datetime.now(timezone.utc)

    return host


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
        capsys,
    ):
        """
        Test basic report generation for all formats.
        """
        mock_get_hosts([sample_host])

        code = report.app(
            ["generate", "--format", format_name], result_action="return_value"
        )
        assert code == 0

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
        assert expected_output in capsys.readouterr().out

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
        code = report.app(args, result_action="return_value")
        assert code == 0

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

        code = report.app(
            ["generate", "--format", "json", flag], result_action="return_value"
        )
        assert code == 0

        mock_renderer.render_json.assert_called_once()
        call_args = mock_renderer.render_json.call_args[0]
        passed_hosts = call_args[0]

        assert len(passed_hosts) == 1
        assert passed_hosts[0].name == "test-host"

    def test_generate_with_specific_hosts_filtered_scope(
        self, mocker, mock_get_hosts, mock_renderer, sample_host
    ):
        """
        Test that specifying hosts on command line results in ReportScope.filtered
        """
        mock_get_hosts([sample_host])

        # Wire the inventory so the HostArg converter resolves "test-host".
        fake_inventory = mocker.Mock()
        fake_inventory.get_host.side_effect = lambda name: (
            sample_host if name == "test-host" else None
        )
        mocker.patch.object(utils_module.context, "inventory", fake_inventory)

        code = report.app(
            ["generate", "--format", "json", "test-host"],
            result_action="return_value",
        )
        assert code == 0

        mock_renderer.render_json.assert_called_once_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.full,
            report_scope=ReportScope.filtered,
            navigation=True,
        )

    @pytest.mark.parametrize(
        "hosts",
        ["unsupported_hosts", None],
        ids=["no_supported_hosts", "host_lookup_failure"],
    )
    def test_generate_error_cases(self, mock_get_hosts, unsupported_host, hosts):
        """
        Test error handling for various failure scenarios.

        get_hosts_or_all returns None when no usable hosts are found (or the
        inventory is empty), which the command treats as an input error.
        """
        # get_hosts_or_all returns None for both error scenarios
        mock_get_hosts(None)

        code = report.app(
            ["generate", "--format", "json"], result_action="return_value"
        )
        assert code == 1  # Input error: no hosts to report on

    @pytest.mark.parametrize(
        "quiet_flag,expect_message",
        [
            (False, True),
            (True, False),
        ],
        ids=["no_quiet", "quiet"],
    )
    def test_updates_only_with_no_matching_hosts(
        self,
        mock_get_hosts,
        mock_renderer,
        empty_host,
        quiet_flag,
        expect_message,
        capsys,
    ):
        """
        Test --updates-only behavior when no hosts have updates
        """
        mock_get_hosts([empty_host])
        mock_renderer.render_json.return_value = "[]"

        args = ["generate", "--format", "json", "--updates-only"]
        if quiet_flag:
            args.append("--quiet")

        code = report.app(args, result_action="return_value")
        assert code == 0

        captured = capsys.readouterr()
        if expect_message:
            assert "No hosts with available updates found" in captured.err
        else:
            assert captured.err == ""
            assert captured.out.strip() == "[]"  # Empty JSON array rendered

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

        code = report.app(
            ["generate", "--format", "json", flag], result_action="return_value"
        )

        assert code == 0
        mock_renderer.render_json.assert_called_with(
            [sample_host],
            hosts_count=1,
            report_type=ReportType.security_only,
            report_scope=ReportScope.complete,
            navigation=True,
        )

    def test_security_updates_only_filters_hosts(
        self, mock_get_hosts, mock_renderer, empty_host, capsys
    ):
        """Test that hosts without security updates are filtered out."""
        mock_get_hosts([empty_host])

        code = report.app(
            ["generate", "--format", "json", "--security-updates-only"],
            result_action="return_value",
        )

        assert code == 0
        assert "No hosts with security updates found" in capsys.readouterr().err

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
        capsys,
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

        code = report.app(args, result_action="return_value")
        assert code == 0

        assert output_file.exists()
        assert output_file.read_text() == '{"test": "data"}'

        out = capsys.readouterr().out
        if expect_stdout:
            # Rich formats JSON with indentation, so check for key content
            assert '"test"' in out and '"data"' in out
        else:
            assert out == ""

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
        capsys,
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

        code = report.app(args, result_action="return_value")

        assert code == 0
        captured = capsys.readouterr()
        assert captured.out == ""  # No stdout when using --output
        assert output_file.read_text() == "test output"

        if expect_message:
            assert "Report of type" in captured.err and "saved to" in captured.err
        else:
            assert (
                "Report of type" not in captured.err and "saved to" not in captured.err
            )

    def test_file_output_error_handling(
        self, mock_get_hosts, sample_host, tmp_path, capsys
    ):
        """
        Test file write error handling

        This is supremely basic but it really has the same result
        with any sort of Exception.
        """
        mock_get_hosts([sample_host])

        # Test file write error with invalid path (nonexistent parent dirs)
        invalid_path = tmp_path / "nonexistent" / "directory" / "file.json"
        code = report.app(
            ["generate", "--format", "json", "--output", str(invalid_path)],
            result_action="return_value",
        )

        assert code == 2  # Application error: write failed
        assert "Failed to write to" in capsys.readouterr().err

    def test_output_rejects_directory(self, mock_get_hosts, sample_host, tmp_path):
        """
        Test that --output rejects a path that is a directory.

        The Path validator (dir_okay=False) rejects directories during
        argument binding, as an input error.
        """
        mock_get_hosts([sample_host])

        with pytest.raises(SystemExit) as exc_info:
            report.app(["generate", "--format", "json", "--output", str(tmp_path)])

        assert exc_info.value.code == 1  # Input error from validator

    def test_tee_requires_output(self, mock_get_hosts, sample_host, capsys):
        """--tee without --output is rejected by the validator"""
        mock_get_hosts([sample_host])

        with pytest.raises(SystemExit) as exc_info:
            report.app(["generate", "--tee"])

        assert exc_info.value.code == 1
        assert "--tee requires --output" in capsys.readouterr().err

    def test_no_navigation_requires_html(self, mock_get_hosts, sample_host, capsys):
        """--no-navigation only applies to HTML output only"""
        mock_get_hosts([sample_host])

        with pytest.raises(SystemExit) as exc_info:
            report.app(["generate", "--format", "text", "--no-navigation"])

        assert exc_info.value.code == 1
        assert (
            "--no-navigation only applies to --format html" in capsys.readouterr().err
        )

    def test_filters_mutually_exclusive(self, mock_get_hosts, sample_host, capsys):
        """--updates-only and --security-updates-only are mutually exclusive."""
        mock_get_hosts([sample_host])

        with pytest.raises(SystemExit) as exc_info:
            report.app(["generate", "--updates-only", "--security-updates-only"])

        assert exc_info.value.code == 1
        assert "Mutually exclusive arguments" in capsys.readouterr().err


class TestSchemaCommand:
    """Tests for the report schema command."""

    def test_schema_to_stdout(self, capsys):
        """Schema is printed to stdout as valid JSON matching the canonical schema."""
        code = report.app(["schema"], result_action="return_value")
        assert code == 0

        # Rich pretty-prints the JSON; reparsing confirms validity and identity.
        data = json.loads(capsys.readouterr().out)
        assert data == get_host_report_schema()

    def test_schema_to_file(self, tmp_path):
        """--output writes the schema verbatim to a file."""
        target = tmp_path / "host-report.schema.json"

        code = report.app(
            ["schema", "--output", str(target)], result_action="return_value"
        )
        assert code == 0

        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == get_host_report_schema()

    def test_schema_load_failure(self, mocker, capsys):
        """A schema load error surfaces as an application error (exit 2)."""
        mocker.patch(
            "exosphere.commands.report.get_host_report_schema",
            side_effect=FileNotFoundError("Oops everything broke"),
        )

        code = report.app(["schema"], result_action="return_value")
        assert code == 2
        assert "Failed to load JSON schema" in capsys.readouterr().err


class TestStatusCommand:
    """Tests for the report status command."""

    def test_empty_inventory(self, mock_inventory, capsys):
        """An empty inventory reports as such and exits cleanly."""
        mock_inventory.hosts = []

        code = report.app(["status"], result_action="return_value")
        assert code == 0
        assert "No hosts in inventory." in capsys.readouterr().out

    def test_all_up_to_date(self, mock_inventory, capsys):
        """With no pending updates, the summary states everything is current."""
        mock_inventory.hosts = [_status_host("a"), _status_host("b")]

        code = report.app(["status"], result_action="return_value")
        assert code == 0

        out = capsys.readouterr().out
        assert "All hosts are up to date." in out

    def test_pending_updates_and_security(self, mock_inventory, capsys):
        """Update counts and security host count are summarized."""
        sec = Update(name="curl", current_version="1", new_version="2", security=True)
        reg = Update(name="vim", current_version="1", new_version="2", security=False)
        mock_inventory.hosts = [
            _status_host("a", updates=[sec, reg]),
            _status_host("b", updates=[reg]),
            _status_host("c"),
        ]

        code = report.app(["status"], result_action="return_value")
        assert code == 0

        out = capsys.readouterr().out
        assert "2 of 3 hosts have pending updates" in out
        assert "1 with security updates" in out

    def test_reboot_and_stale_lines(self, mock_inventory, capsys):
        """Pending reboot and stale data each produce their own line."""
        mock_inventory.hosts = [
            _status_host("a", needs_reboot=True),
            _status_host("b", stale=True),
        ]

        code = report.app(["status"], result_action="return_value")
        assert code == 0

        out = capsys.readouterr().out
        assert "1 host has a pending reboot." in out
        assert "1 host has stale data" in out
