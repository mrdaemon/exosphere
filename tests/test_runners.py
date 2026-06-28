import shlex

from fabric import Config, Connection

from exosphere.runners import ExosphereRemote


class TestExosphereRemote:
    """
    Tests for the ExosphereRemote Fabric runner.
    """

    def _make_runner(self, mocker, context):
        runner = ExosphereRemote(context=context)
        runner.channel = mocker.Mock()
        return runner

    def _sent_payload(self, runner) -> str:
        sent = runner.channel.exec_command.call_args.args[0]
        assert sent.startswith("/bin/sh -c ")
        return shlex.split(sent)[2]

    def test_wraps_command_in_posix_sh_with_locale(self, mocker):
        """The command is wrapped and the locale exported ahead of it."""
        context = mocker.Mock()
        context.exosphere_locale = "C.UTF-8"
        runner = self._make_runner(mocker, context)

        runner.send_start_message("dnf check-update | grep '^Inst'")

        assert self._sent_payload(runner) == (
            "export LC_ALL=C.UTF-8 LANG=C.UTF-8 && dnf check-update | grep '^Inst'"
        )

    def test_privileged_command_reaches_sudo_verbatim(self, mocker):
        """
        For a sudo invocation, the command sudo receives (after the wrap) is
        the verbatim privileged command, preserving sudoers matching.

        The message is built on what Fabric does in source.
        """
        context = mocker.Mock()
        context.exosphere_locale = "C"
        runner = self._make_runner(mocker, context)

        runner.send_start_message("sudo -S -p '[sudo] password: ' -- pkg update -q")

        assert self._sent_payload(runner) == (
            "export LC_ALL=C LANG=C && sudo -S -p '[sudo] password: ' -- pkg update -q"
        )

    def test_defaults_to_C_when_locale_absent(self, mocker):
        """A connection without exosphere_locale falls back to the C locale."""
        context = mocker.Mock(spec=[])  # no exosphere_locale attribute
        runner = self._make_runner(mocker, context)

        runner.send_start_message("uname -s")

        assert self._sent_payload(runner) == "export LC_ALL=C LANG=C && uname -s"

    def test_reads_locale_from_real_connection_config(self, mocker):
        """
        The locale carried in a real Fabric Connection's config (the way
        Host.connection sets it) reaches the wrapped payload.

        This drives a real Connection rather than a Mock, exercising invoke's
        config proxying that the Host unit tests stub out.
        """
        cx = Connection(
            "localhost",
            config=Config(overrides={"exosphere_locale": "C.UTF-8"}),
        )
        runner = self._make_runner(mocker, cx)

        runner.send_start_message("uname -s")

        assert self._sent_payload(runner) == (
            "export LC_ALL=C.UTF-8 LANG=C.UTF-8 && uname -s"
        )

    def test_payload_is_shlex_quoted_as_single_argument(self, mocker):
        """
        The wrapped payload is handed to ``/bin/sh -c`` as a single
        shell-quoted argument, so shell metacharacters in the command never
        escape the quoting.
        """
        context = mocker.Mock()
        context.exosphere_locale = "C"
        runner = self._make_runner(mocker, context)

        nasty = "echo $(id) && rm -rf / ; `whoami` | tee 'x'"
        runner.send_start_message(nasty)

        sent = runner.channel.exec_command.call_args.args[0]
        tokens = shlex.split(sent)

        # None of our nasty metacharacters have escaped to more tokens
        assert len(tokens) == 3
        assert tokens[:2] == ["/bin/sh", "-c"]
        assert tokens[2] == f"export LC_ALL=C LANG=C && {nasty}"
