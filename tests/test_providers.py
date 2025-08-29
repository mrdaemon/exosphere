import logging

import pytest

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers import Apt, Dnf, Pkg, PkgManagerFactory, Yum


class TestPkgManagerFactory:
    @pytest.mark.parametrize(
        "name, expected_class",
        [("apt", Apt), ("pkg", Pkg), ("dnf", Dnf), ("yum", Yum)],
        ids=["apt", "pkg", "dnf", "yum"],
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
        assert len(registry) == 4
        assert "apt" in registry
        assert "pkg" in registry
        assert "dnf" in registry
        assert "yum" in registry

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
            "apt-get update", hide=True, warn=True
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

    def test_reposync(self, mock_connection):
        """
        Test the reposync method of the Pkg provider.
        This method is a no-op for FreeBSD, since pkg automatically
        syncs the repositories on update checks.
        """

        pkg = Pkg()
        result = pkg.reposync(mock_connection)

        assert result is True

    def test_get_updates(self, mock_pkg_output):
        """
        Test the get_updates method of the Pkg provider.
        The data is provided by the mock_pkg_output fixture.

        Note: Closely coupled with implementation due to use
        of side effect to mock to two separate calls to the
        mock_connection.run method.
        """
        pkg = Pkg()

        try:
            updates: list[Update] = pkg.get_updates(mock_pkg_output)
        except DataRefreshError as e:
            pytest.fail(f"DataRefreshError should not be raised, got: {e}")

        assert len(updates) == 20

        # new package
        assert updates[0].name == "bash-completion-zfs"
        assert updates[0].current_version is None
        assert updates[0].new_version == "2.3.1"
        assert not updates[0].security

        # normal package update
        assert updates[1].name == "btop"
        assert updates[1].current_version == "1.4.1"
        assert updates[1].new_version == "1.4.3"
        assert not updates[1].security

        # Ensure security updates are correctly identified
        assert updates[13].name == "py311-h11"
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
        mock_kernel.stdout = "kernel.x86_64\t5.14.0-570.18.1.el9_6\tbaseos"
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
        output = "kernel.x86_64\t5.14.0-570.18.1.el9_6\tbaseos"

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
        assert any(f"{expected_command} repoquery" in cmd for cmd in command_calls)

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
