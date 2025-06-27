import pytest

from exosphere.data import Update
from exosphere.errors import DataRefreshError
from exosphere.providers import Apt, Dnf, Pkg, PkgManagerFactory


class TestPkgManagerFactory:
    @pytest.mark.parametrize(
        "name, expected_class",
        [("apt", Apt), ("pkg", Pkg), ("dnf", Dnf), ("yum", Dnf)],
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


class TestAptProvider:
    @pytest.fixture
    def mock_connection(self, mocker):
        """
        Fixture to mock the Fabric Connection object.
        """
        mock_cx = mocker.patch("fabric.Connection", autospec=True)
        mock_cx.run.return_value.failed = False
        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value.failed = True
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with sudo.
        """
        mock_connection.sudo.return_value.failed = False
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo_failed(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with sudo and a failed run.
        """
        mock_connection.sudo.return_value.failed = True
        return mock_connection

    @pytest.fixture
    def mock_pkg_output(self, mocker, mock_connection):
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
    def mock_pkg_output_no_updates(self, mocker, mock_connection):
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
            ("mock_connection_sudo", True),
            ("mock_connection_sudo_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, mocker, request, connection_fixture, expected):
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

    def test_get_updates(self, mocker, mock_pkg_output):
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

    def test_get_updates_no_updates(self, mocker, mock_pkg_output_no_updates):
        """
        Test the get_updates method of the Apt provider when no updates are available.
        """
        apt = Apt()

        updates: list[Update] = apt.get_updates(mock_pkg_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mocker, mock_connection):
        """
        Test the get_updates method of the Apt provider when the query fails.
        """
        apt = Apt()
        mock_connection.run.return_value.failed = True
        mock_connection.run.return_value.stderr = "Generic error"

        with pytest.raises(DataRefreshError):
            apt.get_updates(mock_connection)

    def test_get_updates_invalid_output(self, mocker, mock_connection):
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
        mock_cx = mocker.patch("exosphere.providers.freebsd.Connection", autospec=True)
        mock_cx.run.return_value.failed = False
        return mock_cx

    @pytest.fixture
    def mock_connection_failed(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with a failed run.
        """
        mock_connection.run.return_value.failed = True
        mock_connection.run.return_value.stderr = "Generic error"
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo(self, mocker, mock_connection):
        """
        Fixture to mock the Fabric Connection object with sudo.
        """
        mock_connection.sudo.return_value.failed = False
        return mock_connection

    @pytest.fixture
    def mock_connection_sudo_failed(self, mocker, mock_connection):
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

        mock_connection.run.side_effect = [mock_audit, mock_packages]

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

        mock_connection.run.side_effect = [mock_audit, mock_packages]
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

        mock_connection.run.side_effect = [mock_audit, mock_packages]
        return mock_connection

    def test_reposync(self, mocker, mock_connection):
        """
        Test the reposync method of the Pkg provider.
        This method is a no-op for FreeBSD, since pkg automatically
        syncs the repositories on update checks.
        """

        pkg = Pkg()
        result = pkg.reposync(mock_connection)

        assert result is True

    def test_get_updates(self, mocker, mock_pkg_output):
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

    def test_get_updates_no_updates(self, mocker, mock_pkg_output_no_updates):
        """
        Test the get_updates method of the Pkg provider when no updates are available.
        """
        pkg = Pkg()

        updates: list[Update] = pkg.get_updates(mock_pkg_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mocker, mock_connection_failed):
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
    def test_get_updates_invalid_output(self, mocker, mock_connection, output):
        """
        Test the get_updates method of the Pkg provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        pkg = Pkg()
        mock_connection.run.return_value.stdout = output

        results = pkg.get_updates(mock_connection)

        assert results == []

    def test_get_updates_nonzero_exit_audit(self, mocker, mock_pkg_output_audit_failed):
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
        mock_cx = mocker.patch("fabric.Connection", autospec=True)
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
    def mock_dnf_output_return(self, mocker, mock_connection):
        """
        Fixture to mock the output of the dnf command enumerating packages.
        """
        output = """

        emacs-filesystem.noarch               1:27.2-13.el9_6                   appstream
        expat.x86_64                          2.5.0-5.el9_6                     baseos
        git.x86_64                            2.47.1-2.el9_6                    appstream
        git-core.x86_64                       2.47.1-2.el9_6                    appstream
        git-core-doc.noarch                   2.47.1-2.el9_6                    appstream
        kernel.x86_64                         5.14.0-570.18.1.el9_6             baseos
        kernel-core.x86_64                    5.14.0-570.18.1.el9_6             baseos
        kernel-modules.x86_64                 5.14.0-570.18.1.el9_6             baseos
        kernel-modules-core.x86_64            5.14.0-570.18.1.el9_6             baseos
        kernel-tools.x86_64                   5.14.0-570.18.1.el9_6             baseos
        kernel-tools-libs.x86_64              5.14.0-570.18.1.el9_6             baseos
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
    def mock_dnf_current_versions_return(self, mocker, mock_connection):
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
        kernel.x86_64                         5.14.0-502.35.1.el9_5             @baseos
        kernel-core.x86_64                    5.14.0-502.35.1.el9_5             @baseos
        kernel-modules.x86_64                 5.12.0-502.35.1.el9_5             @baseos
        kernel-modules.x86_64                 5.13.0-502.35.1.el9_5             @baseos
        kernel-modules.x86_64                 5.14.0-502.35.1.el9_5             @baseos
        kernel-modules-core.x86_64            5.14.0-502.35.1.el9_5             @baseos
        kernel-tools.x86_64                   5.14.0-502.35.1.el9_5             @baseos
        kernel-tools-libs.x86_64              5.14.0-502.35.1.el9_5             @baseos
        """

        mock_return = mocker.MagicMock()
        mock_return.stdout = output
        mock_return.failed = False
        mock_return.return_code = 0

        return mock_return

    @pytest.fixture
    def mock_dnf_security_output_return(self, mocker, mock_connection):
        """
        Fixture to mock the output of the dnf command for security updates.
        """
        output = """

        kernel.x86_64                        5.14.0-570.18.1.el9_6              baseos
        kernel-core.x86_64                   5.14.0-570.18.1.el9_6              baseos
        kernel-modules.x86_64                5.14.0-570.18.1.el9_6              baseos
        kernel-modules-core.x86_64           5.14.0-570.18.1.el9_6              baseos
        kernel-tools.x86_64                  5.14.0-570.18.1.el9_6              baseos
        kernel-tools-libs.x86_64             5.14.0-570.18.1.el9_6              baseos
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
        mock_connection.run.return_value = mocker.MagicMock()
        mock_connection.run.return_value.stdout = ""
        mock_connection.run.return_value.return_code = 0

        return mock_connection

    @pytest.fixture
    def run_side_effect_normal(
        self,
        mocker,
        mock_dnf_output_return,
        mock_dnf_security_output_return,
        mock_dnf_current_versions_return,
    ):
        def _side_effect(cmd, *args, **kwargs):
            if "dnf check-update --security" in cmd:
                return mock_dnf_security_output_return
            elif "dnf check-update" in cmd:
                return mock_dnf_output_return
            elif "dnf list installed" in cmd:
                return mock_dnf_current_versions_return

        return _side_effect

    @pytest.mark.parametrize(
        "connection_fixture, expected",
        [
            ("mock_connection", True),
            ("mock_connection_failed", False),
        ],
        ids=["success", "failure"],
    )
    def test_reposync(self, mocker, request, connection_fixture, expected):
        """
        Test the reposync method of the DNF provider.
        This method is a no-op for Red Hat-based systems, since dnf automatically
        syncs the repositories on update checks.
        """
        mock_connection = request.getfixturevalue(connection_fixture)

        dnf = Dnf()
        result = dnf.reposync(mock_connection)

        mock_connection.run.assert_called_once_with(
            "dnf makecache", hide=True, warn=True
        )

        assert result is expected

    def test_get_updates(self, mocker, mock_connection, run_side_effect_normal):
        """
        Test the get_updates method of the DNF provider.
        The data is provided by the mock_dnf_output fixture.
        """
        dnf = Dnf()

        # Setup side effects for the connection object, use the security output first
        mock_connection.run.side_effect = run_side_effect_normal

        try:
            updates: list[Update] = dnf.get_updates(mock_connection)
        except DataRefreshError as e:
            pytest.fail(f"DataRefreshError should not be raised, got: {e}")

        assert len(updates) == 11
        assert updates[0].name == "emacs-filesystem.noarch"
        assert updates[0].new_version == "1:27.2-13.el9_6"
        assert updates[0].current_version == "1:27.1-10.el9_6"
        assert not updates[0].security
        assert updates[5].name == "kernel.x86_64"
        assert updates[5].new_version == "5.14.0-570.18.1.el9_6"
        assert updates[5].current_version == "5.14.0-502.35.1.el9_5"
        assert updates[5].security

    def test_get_updates_no_updates(self, mocker, mock_dnf_output_no_updates):
        """
        Test the get_updates method of the DNF provider when no updates are available.
        """
        dnf = Dnf()

        updates: list[Update] = dnf.get_updates(mock_dnf_output_no_updates)

        assert updates == []

    def test_get_updates_query_failed(self, mocker, mock_connection_failed):
        """
        Test the get_updates method of the DNF provider when the query fails.
        """
        dnf = Dnf()

        with pytest.raises(DataRefreshError):
            dnf.get_updates(mock_connection_failed)

    def test_get_updates_invalid_output(self, mocker, mock_connection):
        """
        Test the get_updates method of the DNF provider with invalid output.
        Unparsable output in lines should be ignored.
        """
        dnf = Dnf()
        mock_connection.run.return_value.stdout = "Invalid output"

        results = dnf.get_updates(mock_connection)

        assert results == []
