import logging

import pytest

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers import Apt, Dnf, Pkg, PkgAdd, PkgManagerFactory, Yum


class TestPkgManagerFactory:
    @pytest.mark.parametrize(
        "name, expected_class",
        [("apt", Apt), ("pkg", Pkg), ("pkg_add", PkgAdd), ("dnf", Dnf), ("yum", Yum)],
        ids=["apt", "pkg", "pkg_add", "dnf", "yum"],
    )
    def test_create(self, name, expected_class):
        """
        Test the PkgManagerFactory to create package manager instances.
        """
        pkg_manager = PkgManagerFactory.create(name)
        assert isinstance(pkg_manager, expected_class)

    def test_create_invalid(self):
        """
        Test the PkgManagerFactory with an invalid package manager name.
        """
        with pytest.raises(ValueError):
            PkgManagerFactory.create("invalid_pkg_manager")

    def test_get_registry(self):
        """
        Test the ability to get available package managers.
        """
        registry = PkgManagerFactory.get_registry()

        assert isinstance(registry, dict)
        assert len(registry) == 5
        assert "apt" in registry
        assert "pkg" in registry
        assert "dnf" in registry
        assert "yum" in registry
        assert "pkg_add" in registry

        # Ensure we got a copy and not the original
        registry["apt"] = "modified"  # type: ignore
        assert PkgManagerFactory.get_registry()["apt"] != "modified"


class TestAptProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx_class = mocker.patch(
            "exosphere.providers.debian.Connection", autospec=True
        )
        mock_cx = mock_cx_class.return_value

        # Context manager behavior should return the same mock
        mock_cx.__enter__.return_value = mock_cx
        mock_cx.__exit__.return_value = False  # Don't suppress exceptions

        # Default to successful run
        mock_cx.run.return_value.failed = False
        mock_cx.sudo.return_value.failed = False

        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value.failed = True
        mock_connection.sudo.return_value.failed = True
        return mock_connection

    @pytest.fixture
    def mock_pkg_output(self, mock_connection):
        """
        Fixture to mock the output of the apt command enumerating packages.
        """
        output = """
        
        Inst base-files [12.4+deb12u10] (12.4+deb12u11 Debian:12.11/stable [arm64])
        Inst bash [5.2.15-2+b7] (5.2.15-2+b8 Debian:12.11/stable [arm64])
        Inst login [1:4.13+dfsg1-1+b1] (1:4.13+dfsg1-1+deb12u1 Debian:12.11/stable [arm64])
        Inst libdtovl0 (20250514-1~bookworm Raspberry Pi Foundation:stable [arm64])
        Inst libgpiolib0 (20250514-1~bookworm Raspberry Pi Foundation:stable [arm64])

        Inst passwd [1:4.13+dfsg1-1+b1] (1:4.13+dfsg1-1+deb12u1 Debian:12.11/stable [arm64])
        Inst initramfs-tools [0.142+rpt3+deb12u1] (0.142+rpt3+deb12u3 Raspberry Pi Foundation:stable [all])
        Inst big-patch [1.0-1] (1.0-2 Debian:12.11/bookworm-security [arm64])
        """
        mock_connection.run.return_value.stdout = output
        return mock_connection

    @pytest.fixture
    def mock_pkg_output_no_updates(self, mock_connection):
        """
        Fixture to mock the output of the apt command when no updates are available.
        """
        mock_connection.run.return_value.stdout = ""
        mock_connection.run.return_value.failed = True  # grep will fail!
        mock_connection.run.return_value.stderr = ""  # but no error message

        return mock_connection

    @pytest.mark.parametrize(
        "connection_fixture, expected",
        [
            ("mock_connection", True),
            ("mock_connection_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, request, connection_fixture, expected):
        """
        Test the reposync method of the Apt provider.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        apt = Apt()
        result = apt.reposync(mock_connection)

        mock_connection.sudo.assert_called_once_with(
            "/usr/bin/apt-get update", hide=True, warn=True
        )
        assert result is expected

    def test_get_updates(self, mock_pkg_output):
        """
        Test the get_updates method of the Apt provider.
        """
        apt = Apt()
        updates: list[Update] = apt.get_updates(mock_pkg_output)

        assert len(updates) == 8
        assert updates[0].name == "base-files"
        assert updates[0].current_version == "12.4+deb12u10"
        assert updates[0].new_version == "12.4+deb12u11"
        assert updates[0].source == "Debian:12.11/stable"
        assert not updates[0].security

        # Ensure new package updates are correctly identified
        assert updates[3].name == "libdtovl0"
        assert updates[3].current_version is None
        assert updates[3].new_version == "20250514-1~bookworm"
        assert updates[3].source == "Raspberry Pi Foundation:stable"
        assert not updates[3].security

        # Ensure security updates are correctly identified
        assert updates[7].name == "big-patch"
        assert updates[7].security

    def test_get_updates_no_updates(self, mock_pkg_output_no_updates):
        """
        Test the get_updates method of the Apt provider when no updates are available.
        """
        apt = Apt()

        updates: list[Update] = apt.get_updates(mock_pkg_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mock_connection):
        """
        Test the get_updates method of the Apt provider when the query fails.
        """
        apt = Apt()
        mock_connection.run.return_value.failed = True
        mock_connection.run.return_value.stderr = "Generic error"

        with pytest.raises(DataRefreshError):
            apt.get_updates(mock_connection)

    def test_get_updates_invalid_output(self, mock_connection):
        """
        Test the get_updates method of the Apt provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        apt = Apt()
        mock_connection.run.return_value.stdout = "Invalid output"

        results = apt.get_updates(mock_connection)

        assert results == []


class TestPkgProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx_class = mocker.patch(
            "exosphere.providers.freebsd.Connection", autospec=True
        )
        mock_cx = mock_cx_class.return_value

        # Context manager behavior should return the same mock
        mock_cx.__enter__.return_value = mock_cx
        mock_cx.__exit__.return_value = False  # Don't supress exceptions

        # Default to successful run
        mock_cx.run.return_value.failed = False

        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value.failed = True
        mock_connection.run.return_value.stderr = "Generic error"
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo(self, mock_connection):
        """
        Fixture to mock the Fabric Connection object with sudo.
        """
        mock_connection.sudo.return_value.failed = False
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo_failed(self, mock_connection):
        """
        Fixture to mock the Fabric Connection object with sudo and a failed run.
        """
        mock_connection.sudo.return_value.failed = True
        return mock_connection

    @pytest.fixture
    def mock_pkg_output(self, mocker, mock_connection):
        """
        Fixture to mock the output of the pkg command enumerating packages.
        """
        output = """
        The following 19 package(s) will be affected (of 0 checked):

        Installed packages to be UPGRADED:
                bash-completion-zfs: 2.3.1
                btop: 1.4.1 -> 1.4.3
                cmake: 3.31.6 -> 3.31.7
                cmake-core: 3.31.6 -> 3.31.7
                cmake-doc: 3.31.6 -> 3.31.7
                cmake-man: 3.31.6 -> 3.31.7
                curl: 8.13.0 -> 8.13.0_2
                en-freebsd-doc: 20250425,1 -> 20250509,1
                libgcrypt: 1.11.0 -> 1.11.1
                mpdecimal: 4.0.0 -> 4.0.1
                p5-URI: 5.31 -> 5.32
                pciids: 20250309 -> 20250415
                py311-cryptography: 44.0.1,1 -> 44.0.2,1
                py311-h11: 0.14.0_1 -> 0.16.0
                py311-httpcore: 1.0.7 -> 1.0.9
                py311-markdown: 3.6 -> 3.7
                py311-typing-extensions: 4.13.1 -> 4.13.2
                smartmontools: 7.4_2 -> 7.5
                vim: 9.1.1265 -> 9.1.1378
                xxd: 9.1.1265 -> 9.1.1378
                autoconf-2.72 (direct dependency changed: perl5)
                net-snmp-5.9.4_6,1 (direct dependency changed: perl5)

        Number of packages to be upgraded: 19

        77 MiB to be downloaded.

        """
        output_vulnerable = "py311-h11-0.14.0_1"

        mock_audit = mocker.MagicMock()
        mock_audit.failed = True  # Audit returns non-zero exit code on match
        mock_audit.stdout = output_vulnerable
        mock_audit.stderr = ""  # No error message for successful audit

        mock_packages = mocker.MagicMock()
        mock_packages.failed = False
        mock_packages.stdout = output

        def side_effect(cmd, *args, **kwargs):
            if "pkg audit" in cmd:
                return mock_audit
            elif "pkg upgrade" in cmd:
                return mock_packages
            else:
                # Default empty response
                result = mocker.MagicMock()
                result.stdout = ""
                result.failed = False
                result.return_code = 0
                return result

        mock_connection.run.side_effect = side_effect

        return mock_connection

    @pytest.fixture
    def mock_pkg_output_with_repo(self, mocker, mock_connection):
        """
        Fixture to mock the output of recent pkg with repo tag in output
        """
        output = """
        The following 19 package(s) will be affected (of 0 checked):

        Installed packages to be UPGRADED:
                bash-completion-zfs: 2.3.1 [FreeBSD]
                btop: 1.4.1 -> 1.4.3 [FreeBSD]
                cmake: 3.31.6 -> 3.31.7 [FreeBSD]
                cmake-core: 3.31.6 -> 3.31.7 [FreeBSD]
                cmake-doc: 3.31.6 -> 3.31.7 [FreeBSD]
                cmake-man: 3.31.6 -> 3.31.7 [FreeBSD]
                curl: 8.13.0 -> 8.13.0_2 [FreeBSD]
                en-freebsd-doc: 20250425,1 -> 20250509,1 [FreeBSD]
                libgcrypt: 1.11.0 -> 1.11.1 [FreeBSD]
                mpdecimal: 4.0.0 -> 4.0.1 [FreeBSD]
                p5-URI: 5.31 -> 5.32 [FreeBSD]
                pciids: 20250309 -> 20250415 [FreeBSD]
                py311-cryptography: 44.0.1,1 -> 44.0.2,1 [FreeBSD]
                py311-h11: 0.14.0_1 -> 0.16.0 [FreeBSD]
                py311-httpcore: 1.0.7 -> 1.0.9 [FreeBSD]
                py311-markdown: 3.6 -> 3.7 [FreeBSD]
                py311-typing-extensions: 4.13.1 -> 4.13.2 [FreeBSD]
                smartmontools: 7.4_2 -> 7.5 [FreeBSD]
                vim: 9.1.1265 -> 9.1.1378 [FreeBSD]
                xxd: 9.1.1265 -> 9.1.1378 [FreeBSD]
                autoconf-2.72 [FreeBSD] (direct dependency changed: perl5)
                net-snmp-5.9.4_6,1 [FreeBSD] (direct dependency changed: perl5)

        Number of packages to be upgraded: 19

        77 MiB to be downloaded.

        """
        output_vulnerable = "py311-h11-0.14.0_1"

        mock_audit = mocker.MagicMock()
        mock_audit.failed = True  # Audit returns non-zero exit code on match
        mock_audit.stdout = output_vulnerable
        mock_audit.stderr = ""  # No error message for successful audit

        mock_packages = mocker.MagicMock()
        mock_packages.failed = False
        mock_packages.stdout = output

        def side_effect(cmd, *args, **kwargs):
            if "pkg audit" in cmd:
                return mock_audit
            elif "pkg upgrade" in cmd:
                return mock_packages
            else:
                # Default empty response
                result = mocker.MagicMock()
                result.stdout = ""
                result.failed = False
                result.return_code = 0
                return result

        mock_connection.run.side_effect = side_effect

        return mock_connection

    @pytest.fixture
    def mock_pkg_output_audit_failed(self, mocker, mock_connection):
        """
        Fixture to mock the output of the pkg command when the audit fails.
        This simulates a non-zero exit code with an error message.
        """

        mock_audit = mocker.MagicMock()
        mock_audit.failed = True
        mock_audit.stdout = ""
        mock_audit.stderr = "Generic error"

        mock_packages = mocker.MagicMock()
        mock_packages.failed = False
        mock_packages.stdout = ""

        def side_effect(cmd, *args, **kwargs):
            if "pkg audit" in cmd:
                return mock_audit
            elif "pkg upgrade" in cmd:
                return mock_packages
            else:
                # Default empty response
                result = mocker.MagicMock()
                result.stdout = ""
                result.failed = False
                result.return_code = 0
                return result

        mock_connection.run.side_effect = side_effect
        return mock_connection

    @pytest.fixture
    def mock_pkg_output_no_updates(self, mocker, mock_connection):
        """
        Fixture to mock the output of the pkg command when no updates are available.
        """
        mock_audit = mocker.MagicMock()
        mock_audit.failed = False
        mock_audit.stdout = ""
        mock_audit.stderr = ""

        mock_packages = mocker.MagicMock()
        mock_packages.failed = True
        mock_packages.stderr = ""

        def side_effect(cmd, *args, **kwargs):
            if "pkg audit" in cmd:
                return mock_audit
            elif "pkg upgrade" in cmd:
                return mock_packages
            else:
                # Default empty response
                result = mocker.MagicMock()
                result.stdout = ""
                result.failed = False
                result.return_code = 0
                return result

        mock_connection.run.side_effect = side_effect
        return mock_connection

    @pytest.mark.parametrize(
        "connection_fixture, expected",
        [
            ("mock_connection_sudo", True),
            ("mock_connection_sudo_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, request, connection_fixture, expected):
        """
        Test the reposync method of the Pkg provider.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        pkg = Pkg()
        result = pkg.reposync(mock_connection)

        mock_connection.sudo.assert_called_once_with(
            "/usr/sbin/pkg update -q", hide=True, warn=True
        )

        assert result is expected

    @pytest.mark.parametrize(
        "fixture_name,expected_repo_name",
        [
            ("mock_pkg_output", "Packages Mirror"),
            ("mock_pkg_output_with_repo", "FreeBSD"),
        ],
        ids=["legacy_format", "new_pkg_format"],
    )
    def test_get_updates(self, request, fixture_name, expected_repo_name):
        """
        Test the get_updates method of the Pkg provider.
        Tests both legacy format and new format with repository tags.

        Note: Closely coupled with implementation due to use
        of side effect to mock to two separate calls to the
        mock_connection.run method.
        """
        # Get the fixture dynamically
        mock_output = request.getfixturevalue(fixture_name)

        pkg = Pkg()

        try:
            updates: list[Update] = pkg.get_updates(mock_output)
        except DataRefreshError as e:
            pytest.fail(f"DataRefreshError should not be raised, got: {e}")

        assert len(updates) == 20

        # new package
        assert updates[0].name == "bash-completion-zfs"
        assert updates[0].current_version is None
        assert updates[0].new_version == "2.3.1"
        assert updates[0].source == expected_repo_name
        assert not updates[0].security

        # normal package update
        assert updates[1].name == "btop"
        assert updates[1].current_version == "1.4.1"
        assert updates[1].new_version == "1.4.3"
        assert updates[1].source == expected_repo_name
        assert not updates[1].security

        # Ensure security updates are correctly identified
        assert updates[13].name == "py311-h11"
        assert updates[13].source == expected_repo_name
        assert updates[13].security

    def test_get_updates_no_updates(self, mock_pkg_output_no_updates):
        """
        Test the get_updates method of the Pkg provider when no updates are available.
        """
        pkg = Pkg()

        updates: list[Update] = pkg.get_updates(mock_pkg_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mock_connection_failed):
        """
        Test the get_updates method of the Pkg provider when the query fails.
        """
        pkg = Pkg()

        with pytest.raises(DataRefreshError):
            pkg.get_updates(mock_connection_failed)

    @pytest.mark.parametrize(
        "output",
        ["Invalid output", "Updates are being launched in space", "->", ""],
        ids=[
            "invalid_output_1",
            "invalid_output_2",
            "invalid_output_3",
            "empty_output",
        ],
    )
    def test_get_updates_invalid_output(self, mock_connection, output):
        """
        Test the get_updates method of the Pkg provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        pkg = Pkg()
        mock_connection.run.return_value.stdout = output

        results = pkg.get_updates(mock_connection)

        assert results == []

    def test_get_updates_nonzero_exit_audit(self, mock_pkg_output_audit_failed):
        """
        Test the get_updates method of the Pkg provider when the audit command fails.

        We test this by simulating the combination of a non-zero exit code
        and a non-empty stderr, which is the only way to figure out if the
        audit command genuinely failed.
        """
        pkg = Pkg()

        with pytest.raises(DataRefreshError) as e:
            pkg.get_updates(mock_pkg_output_audit_failed)
            assert (
                str(e.value)
                == "Failed to get vulnerable packages from pkg: Generic error"
            )


class TestPkgAddProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx_class = mocker.patch(
            "exosphere.providers.openbsd.Connection", autospec=True
        )
        mock_cx = mock_cx_class.return_value

        # Context manager behavior should return the same mock
        mock_cx.__enter__.return_value = mock_cx
        mock_cx.__exit__.return_value = False  # Don't supress exceptions

        # Default to successful run
        mock_cx.run.return_value.failed = False

        return mock_cx

    @pytest.fixture
    def mock_pkg_add_output(self, mocker, mock_connection):
        """
        Fixture to mock the output of the pkg_add command enumerating packages.

        From OpenBSD 7.7, only upgradable packages are: curl, htop, isc-bind, libxml
        """
        output = """
        Update candidates: curl-8.13.0 -> curl-8.13.1
        Update candidates: ngtcp2-1.11.0 -> ngtcp2-1.11.0
        Update candidates: nghttp2-1.65.0 -> nghttp2-1.65.0
        Update candidates: nghttp3-1.8.0 -> nghttp3-1.8.0
        Update candidates: desktop-file-utils-0.28p0 -> desktop-file-utils-0.28p0
        Update candidates: glib2-2.82.5 -> glib2-2.82.5
        Update candidates: pcre2-10.44 -> pcre2-10.44
        Update candidates: fio-3.38 -> fio-3.38
        Update candidates: libnfs-5.0.2 -> libnfs-5.0.2
        Update candidates: htop-3.4.0 -> htop-3.4.2
        Update candidates: isc-bind-9.20.11v3 -> isc-bind-9.20.13v3
        Update candidates: liburcu-0.15.1 -> liburcu-0.15.1
        Update candidates: libuv-1.50.0p0 -> libuv-1.50.0p0
        Update candidates: libxml-2.13.8 -> libxml-2.13.9
        Update candidates: json-c-0.18 -> json-c-0.18
        Update candidates: libidn2-2.3.0p0 -> libidn2-2.3.0p0
        Update candidates: libunistring-0.9.7 -> libunistring-0.9.7
        Update candidates: libsodium-1.0.20 -> libsodium-1.0.20
        Update candidates: py3-pyrsistent-0.20.0p0 -> py3-pyrsistent-0.20.0p0
        Update candidates: qemu-ga-9.2.2 -> qemu-ga-9.2.2
        Update candidates: sudo-1.9.17.1p0-gettext -> sudo-1.9.17.1p0-gettext
        Update candidates: updatedb-0p0 -> updatedb-0p0
        Update candidates: vim-9.1.1265-no_x11-python3 -> vim-9.1.1265-no_x11-python3
        """

        mock_packages = mocker.MagicMock()
        mock_packages.failed = False
        mock_packages.stdout = output
        mock_packages.stderr = "pkg_add should be run as root\n"

        return mock_packages

    @pytest.fixture
    def mock_pkg_add_output_no_updates(self, mocker, mock_connection):
        """
        Fixture to mock the output of the pkg_add command when no updates are available.
        """
        mock_output = mocker.MagicMock()
        mock_output.failed = False
        mock_output.stdout = """
        Update candidates: ngtcp2-1.11.0 -> ngtcp2-1.11.0
        Update candidates: nghttp2-1.65.0 -> nghttp2-1.65.0
        Update candidates: nghttp3-1.8.0 -> nghttp3-1.8.0
        Update candidates: desktop-file-utils-0.28p0 -> desktop-file-utils-0.28p0
        Update candidates: glib2-2.82.5 -> glib2-2.82.5
        Update candidates: pcre2-10.44 -> pcre2-10.44
        Update candidates: fio-3.38 -> fio-3.38
        Update candidates: libnfs-5.0.2 -> libnfs-5.0.2
        """
        mock_output.stderr = "pkg_add should be run as root\n"

        return mock_output

    @pytest.fixture
    def mock_pkg_add_output_no_packages(self, mocker, mock_connection):
        """
        Fixture to mock the output of pkg_add when no packages have updates
        and grep returns no matches.
        """
        mock_output = mocker.MagicMock()
        mock_output.failed = True
        mock_output.stdout = ""
        mock_output.stderr = "pkg_add should be run as root\n"
        mock_output.return_code = 1

        return mock_output

    @pytest.fixture
    def mock_system_stable_or_release(self, mocker):
        """
        Fixture to mock the output of syspatch to return a stable or release version
        """
        mock_version = mocker.MagicMock()
        mock_version.failed = False
        mock_version.stdout = ""
        mock_version.stderr = ""

        return mock_version

    @pytest.fixture
    def mock_system_current(self, mocker):
        """
        Fixture to mock the output of syspatch to return a current version
        """
        mock_version = mocker.MagicMock()
        mock_version.failed = True
        mock_version.stdout = ""
        mock_version.stderr = "syspatch: Unsupported release: 7.8-beta"

        return mock_version

    @pytest.fixture
    def mock_pkg_add_output_connection_stable(
        self, mock_connection, mock_pkg_add_output, mock_system_stable_or_release
    ):
        """
        Fixture to mock the output of pkg_add add with a stable or release
        version of OpenBSD where all updates should be security updates.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                return mock_pkg_add_output

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_pkg_add_output_connection_current(
        self, mock_connection, mock_pkg_add_output, mock_system_current
    ):
        """
        Fixture to mock the output of pkg_add add with a current
        version of OpenBSD where no updates should be security updates.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_current
            else:
                return mock_pkg_add_output

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_pkg_add_no_updates_connection_stable(
        self,
        mock_connection,
        mock_pkg_add_output_no_updates,
        mock_system_stable_or_release,
    ):
        """
        Fixture to mock the output of pkg_add add with a stable or release
        version of OpenBSD where no updates are available.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                return mock_pkg_add_output_no_updates

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_pkg_add_no_updates_connection_current(
        self, mock_connection, mock_pkg_add_output_no_updates, mock_system_current
    ):
        """
        Fixture to mock the output of pkg_add add with a current
        version of OpenBSD where no updates are available.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_current
            else:
                return mock_pkg_add_output_no_updates

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_pkg_add_no_packages_connection_stable(
        self,
        mock_connection,
        mock_pkg_add_output_no_packages,
        mock_system_stable_or_release,
    ):
        """
        Fixture to mock the output of pkg_add when no packages have updates.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                return mock_pkg_add_output_no_packages

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_pkg_add_no_packages_connection_current(
        self, mock_connection, mock_pkg_add_output_no_packages, mock_system_current
    ):
        """
        Fixture to mock the output of pkg_add when no packages have updates.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_current
            else:
                return mock_pkg_add_output_no_packages

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_connection_uname_failed(
        self, mocker, mock_connection, mock_pkg_add_output
    ):
        """
        Fixture to mock the Fabric Connection object with a failed uname command.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                value = mocker.MagicMock()
                value.failed = True
                value.stderr = "Generic error"
                return value
            else:
                return mock_pkg_add_output

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_connection_pkg_add_query_failed(
        self, mocker, mock_connection, mock_system_stable_or_release
    ):
        """
        Fixture to mock the Fabric Connection object with a failed pkg_add command.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                value = mocker.MagicMock()
                value.failed = True
                value.stderr = "Generic error"
                return value

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.fixture
    def mock_connection_pkg_add_invalid_output(
        self, mocker, mock_connection, mock_system_stable_or_release
    ):
        """
        Fixture to mock the Fabric Connection object with invalid pkg_add output.
        """

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                value = mocker.MagicMock()
                value.failed = False
                value.stdout = "Invalid output"
                return value

        mock_connection.run.side_effect = side_effects
        return mock_connection

    @pytest.mark.parametrize(
        "connection_fixture, expected_security",
        [
            ("mock_pkg_add_output_connection_stable", True),
            ("mock_pkg_add_output_connection_current", False),
        ],
        ids=["stable_or_release", "current"],
    )
    def test_get_updates(self, request, connection_fixture, expected_security):
        """
        Test the get_updates method of the PkgAdd provider.
        """
        mock_pkg_add_output = request.getfixturevalue(connection_fixture)

        pkg_add = PkgAdd()
        updates: list[Update] = pkg_add.get_updates(mock_pkg_add_output)

        assert len(updates) == 4

        assert updates[0].name == "curl"
        assert updates[0].current_version == "8.13.0"
        assert updates[0].new_version == "8.13.1"

        assert updates[1].name == "htop"
        assert updates[1].current_version == "3.4.0"
        assert updates[1].new_version == "3.4.2"

        assert updates[2].name == "isc-bind"
        assert updates[2].current_version == "9.20.11v3"
        assert updates[2].new_version == "9.20.13v3"

        assert updates[3].name == "libxml"
        assert updates[3].current_version == "2.13.8"
        assert updates[3].new_version == "2.13.9"

        for u in updates:
            assert u.security == expected_security

    def test_get_current_generates_warning(
        self, mock_pkg_add_output_connection_current, caplog
    ):
        """
        Test that a warning is logged if the system is tracking -current
        """
        pkg_add = PkgAdd()

        with caplog.at_level(logging.WARNING):
            updates: list[Update] = pkg_add.get_updates(
                mock_pkg_add_output_connection_current
            )

        assert len(updates) == 4
        assert "Host is running unsupported OpenBSD release" in caplog.text
        assert "Security status will not be tracked" in caplog.text

    @pytest.mark.parametrize(
        "connection_fixture",
        [
            "mock_pkg_add_no_updates_connection_stable",
            "mock_pkg_add_no_updates_connection_current",
        ],
        ids=["stable_or_release", "current"],
    )
    def test_get_updates_no_updates(self, request, connection_fixture):
        """
        Test the get_updates method of the PkgAdd provider when no updates are available.
        """
        mock_connection = request.getfixturevalue(connection_fixture)
        pkg_add = PkgAdd()
        updates: list[Update] = pkg_add.get_updates(mock_connection)

        assert updates == []

    @pytest.mark.parametrize(
        "connection_fixture",
        [
            "mock_pkg_add_no_packages_connection_stable",
            "mock_pkg_add_no_packages_connection_current",
        ],
        ids=["stable_or_release", "current"],
    )
    def test_get_updates_no_packages(self, request, connection_fixture, caplog):
        """
        Test the get_updates method of the PkgAdd provider when no upgradable
        packages are found in the output.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        pkg_add = PkgAdd()
        with caplog.at_level(logging.DEBUG):
            updates: list[Update] = pkg_add.get_updates(mock_connection)

        assert updates == []
        assert "No OpenBSD packages with updates" in caplog.text

    @pytest.mark.parametrize(
        "connection_fixture, exception_expected",
        [
            ("mock_connection_uname_failed", "Failed to query OpenBSD version"),
            ("mock_connection_pkg_add_query_failed", "Failed to query OpenBSD pkg_add"),
        ],
        ids=["uname_failure", "pkg_add_failure"],
    )
    def test_get_updates_command_failure(
        self, request, connection_fixture, exception_expected
    ):
        """
        Test the get_updates method of the PkgAdd provider when the query fails.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        pkg_add = PkgAdd()

        with pytest.raises(DataRefreshError, match=exception_expected):
            pkg_add.get_updates(mock_connection)

    def test_get_updates_weird_output(
        self, mocker, mock_connection, mock_system_stable_or_release, caplog
    ):
        """
        Test the get_updates method of the PkgAdd provider with a package
        that unexpectedly changes names between versions.

        That is weird but "legal" and should be a handled case.
        Which we handle by skipping it entirely and logging a warning.
        """

        output = "Update candidates: oldname-1.0 -> newname-2.0"

        def side_effects(cmd, *args, **kwargs):
            if "syspatch" in cmd:
                return mock_system_stable_or_release
            else:
                mock_packages = mocker.MagicMock()
                mock_packages.failed = False
                mock_packages.stdout = output
                return mock_packages

        mock_connection.run.side_effect = side_effects

        pkg_add = PkgAdd()

        with caplog.at_level(logging.WARNING):
            results = pkg_add.get_updates(mock_connection)

        assert results == []
        assert "Unexpected package name change" in caplog.text
        assert "ignoring" in caplog.text

    def test_get_updates_invalid_output(
        self, mock_connection_pkg_add_invalid_output, caplog
    ):
        """
        Test the get_updates method of the PkgAdd provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        pkg_add = PkgAdd()

        with caplog.at_level(logging.DEBUG):
            results = pkg_add.get_updates(mock_connection_pkg_add_invalid_output)

        assert results == []
        assert "Could not parse" in caplog.text

    def test_reposync(self, mock_connection):
        """
        Test the reposync method of the PkgAdd provider.
        It's a big no-op for pkg_add.
        """
        pkg_add = PkgAdd()
        result = pkg_add.reposync(mock_connection)

        assert result is True
        mock_connection.run.assert_not_called()
        mock_connection.sudo.assert_not_called()


class TestDnfProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx_class = mocker.patch(
            "exosphere.providers.redhat.Connection", autospec=True
        )
        mock_cx = mock_cx_class.return_value

        # Context manager behavior should return the same mock
        mock_cx.__enter__.return_value = mock_cx
        mock_cx.__exit__.return_value = False  # Don't supress exceptions

        mock_cx.run.return_value.failed = False
        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value = mocker.MagicMock()
        mock_connection.run.return_value.failed = True
        mock_connection.run.return_value.return_code = 2
        mock_connection.run.return_value.stderr = "Generic error"
        return mock_connection

    @pytest.fixture
    def mock_dnf_output_return(self, mocker):
        """
        Fixture to mock the output of the dnf command enumerating packages.
        """
        output = """

        emacs-filesystem.noarch               1:27.2-13.el9_6                   appstream
        expat.x86_64                          2.5.0-5.el9_6                     baseos
        git.x86_64                            2.47.1-2.el9_6                    appstream
        git-core.x86_64                       2.47.1-2.el9_6                    appstream
        git-core-doc.noarch                   2.47.1-2.el9_6                    appstream
        openssl.x86_64                        3.0.9-16.el9_6                    baseos
        openssl-libs.x86_64                   3.0.9-16.el9_6                    baseos
        systemd.x86_64                        252-18.el9_6                      baseos
        systemd-libs.x86_64                   252-18.el9_6                      baseos
        curl.x86_64                           7.76.1-19.el9_6                   baseos
        curl-minimal.x86_64                   7.76.1-19.el9_6                   baseos
        Obsoleting Packages
        libldb.i686                           4.21.3-3.el9                      baseos
            libldb.x86_64                     2.9.1-2.el9                       @baseos
        """

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = True
        mock_return.return_code = 100

        return mock_return

    @pytest.fixture
    def mock_dnf_current_versions_return(self, mocker):
        """
        Fixture to mock the output of the dnf command for current versions.
        """

        output = """

        Installed Packages
        emacs-filesystem.noarch               1:27.1-10.el9_6                   @appstream
        expat.x86_64                          2.5.0-3.el9_6                     @baseos
        git.x86_64                            2.47.0-1.el9_6                    @appstream
        git-core.x86_64                       2.47.0-1.el9_6                    @appstream
        git-core-doc.noarch                   2.47.1-2.el9_6                    @appstream
        openssl.x86_64                        3.0.9-15.el9_5                    @baseos
        openssl-libs.x86_64                   3.0.9-15.el9_5                    @baseos
        systemd.x86_64                        252-17.el9_5                      @baseos
        systemd-libs.x86_64                   252-17.el9_5                      @baseos
        curl.x86_64                           7.76.1-18.el9_5                   @baseos
        curl-minimal.x86_64                   7.76.1-18.el9_5                   @baseos

        Available packages
        git.x86_64                            2.47.1-2.el9_6                    appstream
        """

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = False
        mock_return.return_code = 0

        return mock_return

    @pytest.fixture
    def mock_dnf_current_versions_kernel_return(self, mocker):
        output = """

        Installed Packages
        kernel.x86_64  5.14.0-502.35.1.el9_5  @baseos
        kernel.x86_64  5.14.0-570.16.1.el9_6  @updates
        kernel.x86_64  5.14.0-570.18.1.el9_6  @updates
        """

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = False
        mock_return.return_code = 0

        return mock_return

    @pytest.fixture
    def mock_dnf_security_output_return(self, mocker):
        """
        Fixture to mock the output of the dnf command for security updates.
        """
        output = """

        openssl.x86_64                       3.0.9-16.el9_6                     baseos
        openssl-libs.x86_64                  3.0.9-16.el9_6                     baseos
        systemd.x86_64                       252-18.el9_6                       baseos
        systemd-libs.x86_64                  252-18.el9_6                       baseos
        kernel.x86_64                        5.14.0-570.18.1.el9_6              baseos
        Obsoleting Packages
        libldb.i686                          4.21.3-3.el9                       baseos
            libldb.x86_64                    2.9.1-2.el9                        @baseos
        """

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = True
        mock_return.return_code = 100

        return mock_return

    @pytest.fixture
    def mock_dnf_output_no_updates(self, mocker, mock_connection):
        """
        Fixture to mock the output of the dnf command when no updates are available.
        """

        # Mock for security updates (empty)
        mock_security = mocker.MagicMock()
        mock_security.stdout = ""
        mock_security.return_code = 0
        mock_security.failed = False

        # Mock for regular updates (empty)
        mock_updates = mocker.MagicMock()
        mock_updates.stdout = ""
        mock_updates.return_code = 0
        mock_updates.failed = False

        # Mock for installed packages (minimal kernel)
        mock_installed = mocker.MagicMock()
        mock_installed.stdout = "kernel.x86_64  5.14.0-570.18.1.el9_6  @baseos"
        mock_installed.return_code = 0
        mock_installed.failed = False

        # Mock for kernel repoquery (same version as installed = no update)
        mock_kernel = mocker.MagicMock()
        mock_kernel.stdout = "kernel.x86_64  5.14.0-570.18.1.el9_6  baseos\n"
        mock_kernel.return_code = 0
        mock_kernel.failed = False

        def side_effect(cmd, *args, **kwargs):
            if "check-update --security" in cmd:
                return mock_security
            elif "check-update" in cmd:
                return mock_updates
            elif "list installed" in cmd:
                return mock_installed
            elif "repoquery" in cmd and "kernel" in cmd:
                return mock_kernel
            else:
                # Default empty response
                result = mocker.MagicMock()
                result.stdout = ""
                result.failed = False
                result.return_code = 0
                return result

        mock_connection.run.side_effect = side_effect

        return mock_connection

    @pytest.fixture
    def mock_dnf_kernel_repoquery_return(self, mocker):
        """
        Fixture to mock the output of the dnf repoquery command for latest kernel.
        Returns the same version as the most recent installed kernel (no update needed).
        """
        output = "kernel.x86_64  5.14.0-570.18.1.el9_6  baseos\n"

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = False
        mock_return.return_code = 0

        return mock_return

    @pytest.fixture
    def run_side_effect_normal(
        self,
        mock_dnf_output_return,
        mock_dnf_security_output_return,
        mock_dnf_current_versions_return,
        mock_dnf_current_versions_kernel_return,
        mock_dnf_kernel_repoquery_return,
    ):
        def _side_effect(cmd, *args, **kwargs):
            if "check-update --security" in cmd:
                return mock_dnf_security_output_return
            elif "check-update" in cmd:
                return mock_dnf_output_return
            elif (
                "list installed" in cmd
                and "kernel" in cmd
                and "kernel.x86_64" not in cmd
            ):
                return mock_dnf_current_versions_kernel_return
            elif "list installed" in cmd:
                return mock_dnf_current_versions_return
            elif "repoquery" in cmd and "kernel" in cmd:
                return mock_dnf_kernel_repoquery_return

        return _side_effect

    @pytest.fixture
    def mock_kernel_test_scenario(self, mocker, mock_connection):
        """
        Flexible fixture factory for kernel test scenarios.
        Returns a function that can create different kernel test setups.
        """

        def create_scenario(
            security_updates="",
            regular_updates="",
            regular_updates_failed=True,
            regular_updates_code=100,
            installed_packages="",
            kernel_query_result="",
            kernel_query_failed=False,
            kernel_query_stderr="",
        ):
            # Mock security updates
            mock_security = mocker.MagicMock()
            mock_security.stdout = security_updates
            mock_security.failed = False
            mock_security.return_code = 0

            # Mock regular updates
            mock_updates = mocker.MagicMock()
            mock_updates.stdout = regular_updates
            mock_updates.failed = regular_updates_failed
            mock_updates.return_code = regular_updates_code

            # Mock installed packages
            mock_versions = mocker.MagicMock()
            mock_versions.stdout = installed_packages
            mock_versions.failed = False
            mock_versions.return_code = 0

            # Mock kernel repoquery
            mock_kernel = mocker.MagicMock()
            mock_kernel.stdout = kernel_query_result
            mock_kernel.failed = kernel_query_failed
            mock_kernel.stderr = kernel_query_stderr
            mock_kernel.return_code = 0 if not kernel_query_failed else 1

            def side_effect(cmd, *args, **kwargs):
                if "check-update --security" in cmd:
                    return mock_security
                elif "check-update" in cmd:
                    return mock_updates
                elif "list installed" in cmd:
                    return mock_versions
                elif "repoquery" in cmd and "kernel" in cmd:
                    return mock_kernel
                else:
                    # Default empty response
                    result = mocker.MagicMock()
                    result.stdout = ""
                    result.failed = False
                    result.return_code = 0
                    return result

            mock_connection.run.side_effect = side_effect
            return mock_connection

        return create_scenario

    @pytest.mark.parametrize(
        "connection_fixture, expected",
        [
            ("mock_connection", True),
            ("mock_connection_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, request, connection_fixture, expected):
        """
        Test the reposync method of the DNF provider.
        This method is a no-op for Red Hat-based systems, since dnf automatically
        syncs the repositories on update checks.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        dnf = Dnf()
        result = dnf.reposync(mock_connection)

        mock_connection.run.assert_called_once_with(
            "dnf --quiet -y makecache --refresh", hide=True, warn=True
        )

        assert result is expected

    def test_get_updates(self, mock_connection, run_side_effect_normal):
        """
        Test the get_updates method of the DNF provider.
        The data is provided by the mock_dnf_output fixture.
        """
        dnf = Dnf()

        # Setup connection side effects for normal run
        # See fixture for details
        mock_connection.run.side_effect = run_side_effect_normal

        try:
            updates: list[Update] = dnf.get_updates(mock_connection)
        except DataRefreshError as e:
            pytest.fail(f"DataRefreshError should not be raised, got: {e}")

        # We should have exactly 11 updates (no kernel update in this scenario)
        assert len(updates) == 11

        # Sort found updates by name as to not deal with ordering
        update_by_name = {u.name: u for u in updates}

        # Check some updates for validity
        emacs = update_by_name["emacs-filesystem.noarch"]
        assert emacs.new_version == "1:27.2-13.el9_6"
        assert emacs.current_version == "1:27.1-10.el9_6"
        assert not emacs.security

        openssl = update_by_name["openssl.x86_64"]
        assert openssl.new_version == "3.0.9-16.el9_6"
        assert openssl.current_version == "3.0.9-15.el9_5"
        assert openssl.security

        # Ensure no kernel updates are reported in this basic scenario
        kernel_updates = [u for u in updates if "kernel" in u.name]
        assert len(kernel_updates) == 0

        # Ensure versions in Available package block are NOT set as
        # currently installed version
        git = update_by_name["git.x86_64"]
        assert git.current_version != "2.47.1-1.el9_5"

    def test_get_updates_no_updates(self, mock_dnf_output_no_updates):
        """
        Test the get_updates method of the DNF provider when no updates are available.
        """
        dnf = Dnf()

        updates: list[Update] = dnf.get_updates(mock_dnf_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mock_connection_failed):
        """
        Test the get_updates method of the DNF provider when the query fails.
        """
        dnf = Dnf()

        with pytest.raises(DataRefreshError):
            dnf.get_updates(mock_connection_failed)

    def test_get_updates_invalid_output(self, mock_connection):
        """
        Test the get_updates method of the DNF provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        dnf = Dnf()
        mock_connection.run.return_value.stdout = "Invalid output"

        results = dnf.get_updates(mock_connection)

        assert results == []

    @pytest.mark.parametrize(
        "provider, expected_command",
        [
            (Dnf, "dnf"),
            (Yum, "yum"),
        ],
        ids=["dnf", "yum"],
    )
    def test_compatibility_mode(
        self,
        mock_dnf_output_no_updates,
        provider,
        expected_command,
    ):
        """
        Test the Yum compat mode of the DNF provider.
        This is not a very exhaustive test, but it ensures the command
        being ran is appropriate.

        If the APIs diverge in the future this will need expanded.
        """

        implementation = provider()

        _ = implementation.get_updates(mock_dnf_output_no_updates)

        assert implementation.pkgbin == expected_command

        # Verify that the correct command binary is used in the calls
        calls = mock_dnf_output_no_updates.run.call_args_list
        command_calls = [call[0][0] for call in calls]

        # Should contain the expected command binary in security, regular updates, and kernel queries
        assert any(
            f"{expected_command} --quiet -y check-update --security" in cmd
            for cmd in command_calls
        )
        assert any(
            f"{expected_command} --quiet -y check-update" in cmd
            and "--security" not in cmd
            for cmd in command_calls
        )
        assert any(
            f"{expected_command} --quiet -y repoquery" in cmd for cmd in command_calls
        )

    def test_get_updates_kernel(self, mock_kernel_test_scenario, caplog):
        """
        Test kernel update scenario: 3 kernels installed, 1 new kernel available.
        This tests the slotted package behavior where kernels are stored as lists.
        """
        dnf = Dnf()

        # Setup scenario with new kernel available + dummy package
        mock_connection = mock_kernel_test_scenario(
            regular_updates="some-package.x86_64\t1.2.3-4.el9\tupdates",
            installed_packages="""
            Installed Packages
            some-package.x86_64  1.2.3-3.el9  @baseos
            kernel.x86_64  5.14.0-502.35.1.el9_5  @baseos
            kernel.x86_64  5.14.0-570.16.1.el9_6  @updates
            kernel.x86_64  5.14.0-570.18.1.el9_6  @updates
            """,
            kernel_query_result="kernel.x86_64\t5.14.0-570.19.1.el9_7\tupdates",
        )

        with caplog.at_level(logging.DEBUG):
            updates = dnf.get_updates(mock_connection)

        # Should have 2 updates total (1 dummy package + 1 kernel)
        assert len(updates) == 2

        # Should have 1 kernel update
        kernel_updates = [u for u in updates if "kernel" in u.name]
        assert len(kernel_updates) == 1

        kernel_update = kernel_updates[0]
        assert kernel_update.name == "kernel.x86_64"
        assert kernel_update.current_version == "5.14.0-570.18.1.el9_6"
        assert kernel_update.new_version == "5.14.0-570.19.1.el9_7"
        assert kernel_update.source == "updates"

        # Verify that the new version was not in the installed kernels
        # (this is what triggers the kernel update logic)
        assert "Found new kernel: 5.14.0-570.19.1.el9_7" in caplog.text

    def test_get_updates_kernel_only_no_regular_updates(
        self, mock_kernel_test_scenario, caplog
    ):
        """
        Test that kernel updates are detected even when there are no regular updates.
        This tests the bug fix for kernel updates being skipped when check-update returns 0.
        """
        dnf = Dnf()

        # Setup scenario with kernel update but no regular updates
        mock_connection = mock_kernel_test_scenario(
            regular_updates="",
            regular_updates_failed=False,
            regular_updates_code=0,
            installed_packages="""
            Installed Packages
            kernel.x86_64  5.14.0-502.35.1.el9_5  @baseos
            kernel.x86_64  5.14.0-570.16.1.el9_6  @updates
            """,
            kernel_query_result="kernel.x86_64\t5.14.0-570.19.1.el9_7\tupdates",
        )

        with caplog.at_level(logging.DEBUG):
            updates = dnf.get_updates(mock_connection)

        # Should have exactly 1 kernel update, no regular updates
        assert len(updates) == 1

        kernel_update = updates[0]
        assert kernel_update.name == "kernel.x86_64"
        assert kernel_update.new_version == "5.14.0-570.19.1.el9_7"
        assert kernel_update.source == "updates"
        assert kernel_update.current_version == "5.14.0-570.16.1.el9_6"

        # Verify the logs show both "No updates available" and kernel detection
        assert "No updates available" in caplog.text
        assert "Found new kernel: 5.14.0-570.19.1.el9_7" in caplog.text

    def test_get_updates_kernel_query_failed(self, mock_kernel_test_scenario):
        """
        Test get_updates when kernel query fails.
        """
        dnf = Dnf()

        # Setup scenario with failed kernel query
        mock_connection = mock_kernel_test_scenario(
            installed_packages="Installed Packages\nkernel.x86_64  5.14.0-502.35.1.el9_5  @baseos",
            kernel_query_failed=True,
            kernel_query_stderr="Repository error",
        )

        with pytest.raises(
            DataRefreshError, match="Failed to retrieve latest kernel from repo"
        ):
            dnf.get_updates(mock_connection)

    def test_get_updates_with_package_clobbering(
        self, mock_kernel_test_scenario, caplog
    ):
        """
        Test get_updates when non-kernel packages get clobbered in current versions.
        """
        dnf = Dnf()

        # Setup scenario with clobbering packages and no kernel update
        mock_connection = mock_kernel_test_scenario(
            installed_packages="""
            Installed Packages
            openssl.x86_64  3.0.9-15.el9_5  @baseos
            openssl.x86_64  3.0.9-16.el9_6  @updates
            kernel.x86_64  5.14.0-502.35.1.el9_5  @baseos
            kernel.x86_64  5.14.0-570.18.1.el9_6  @updates
            """,
            kernel_query_result="kernel.x86_64\t5.14.0-570.18.1.el9_6\tbaseos",
        )

        with caplog.at_level(logging.DEBUG):
            updates = dnf.get_updates(mock_connection)

        # Should have no updates since no newer packages available
        assert len(updates) == 0

        assert (
            "Clobbering 3.0.9-15.el9_5 with 3.0.9-16.el9_6 for package openssl.x86_64"
            in caplog.text
        )

    def test_get_updates_duplicate_packages(self, mock_kernel_test_scenario, caplog):
        """
        Test get_updates when duplicate packages are provided by both kernel
        and regular updates.
        """
        dnf = Dnf()

        # Setup scenario with duplicate packages
        mock_connection = mock_kernel_test_scenario(
            security_updates="""
            Security Updates
            openssl.x86_64  3.0.9-16.el9_6  @updates
            kernel.x86_64  5.14.0-570.19.1.el9_6  @updates
            """,
            regular_updates="""
            openssl.x86_64  3.0.9-16.el9_6  @updates
            kernel.x86_64  5.14.0-570.19.1.el9_6  @updates
            """,
            regular_updates_failed=False,
            installed_packages="""
            Installed Packages
            openssl.x86_64  3.0.9-15.el9_5  @baseos
            kernel.x86_64  5.14.0-502.35.1.el9_5  @baseos
            kernel.x86_64  5.14.0-570.18.1.el9_6  @updates
            """,
            kernel_query_result="kernel.x86_64\t5.14.0-570.19.1.el9_6\tbaseos",
        )

        with caplog.at_level(logging.DEBUG):
            updates = dnf.get_updates(mock_connection)

        # Should have only ONE instance of `kernel.x86_64`
        assert len([u for u in updates if u.name == "kernel.x86_64"]) == 1

        assert (
            "Update for kernel.x86_64 is already in the list, skipping"
        ) in caplog.text
