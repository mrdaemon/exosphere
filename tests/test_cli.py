import sys
import types

from typer.testing import CliRunner

runner = CliRunner()


def test_repl_root(mocker, caplog) -> None:
    import logging

    from exosphere.cli import app as repl_cli

    logging.getLogger("exosphere.cli").setLevel(logging.INFO)
    logging.getLogger("exopshere.cli").addHandler(caplog.handler)

    mock_repl = mocker.patch("exosphere.cli.start_repl")
    result = runner.invoke(repl_cli, [])

    assert result.exit_code == 0
    mock_repl.assert_called_once()
    assert "Starting Exosphere REPL" in caplog.text


def test_repl_version(mocker) -> None:
    """
    Test that --version as an argument to the REPL
    prints the version of Exosphere.

    This is intended to work from command line, but it is handled as a
    special case inside the REPL hooks.
    """
    from exosphere.cli import app as repl_cli

    mocker.patch("exosphere.cli.start_repl")
    result = runner.invoke(repl_cli, ["--version"])
    assert result.exit_code == 0

    # Should mention the version of Exosphere
    assert "Exosphere version" in result.output


def test_ui_start(mocker, caplog) -> None:
    import logging

    from exosphere.commands.ui import app as sub_ui_cli

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)
    mock_ui = mocker.patch("exosphere.commands.ui.ExosphereUi")

    result = runner.invoke(sub_ui_cli, ["start"])

    assert result.exit_code == 0
    mock_ui.return_value.run.assert_called_once()

    assert "Starting Exosphere UI" in caplog.text


def test_ui_webstart(mocker, caplog, monkeypatch) -> None:
    import logging

    from exosphere.commands.ui import app as sub_ui_cli

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)

    # Mock textual_serve and patch it to simulate extras being installed
    fake_server_mod = types.ModuleType("textual_serve.server")
    mock_server_class = mocker.Mock()
    setattr(fake_server_mod, "Server", mock_server_class)
    monkeypatch.setitem(sys.modules, "textual_serve.server", fake_server_mod)

    result = runner.invoke(sub_ui_cli, ["webstart"])

    assert result.exit_code == 0
    mock_server_class.return_value.serve.assert_called_once()
    assert "Starting Exosphere Web UI Server" in caplog.text


def test_ui_webstart_without_extras(mocker, caplog, monkeypatch) -> None:
    import logging

    from exosphere.commands.ui import app as sub_ui_cli

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)

    # Patch textual_serve.server to simulate it not being installed
    monkeypatch.setitem(sys.modules, "textual_serve.server", None)
    mock_console = mocker.patch("exosphere.commands.ui.Console")

    result = runner.invoke(sub_ui_cli, ["webstart"])

    assert result.exit_code == 1
    mock_console.assert_called_with(stderr=True)
    assert (
        "not installed" in result.output.lower()
        or "not installed" in caplog.text.lower()
    )
