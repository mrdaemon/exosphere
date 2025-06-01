from typer.testing import CliRunner

from exosphere.cli import app as repl_cli
from exosphere.commands.ui import app as sub_ui_cli

runner = CliRunner()


def test_repl_root(mocker, caplog) -> None:
    import logging

    logging.getLogger("exosphere.cli").setLevel(logging.INFO)
    logging.getLogger("exopshere.cli").addHandler(caplog.handler)

    mocker.patch("exosphere.cli.make_click_shell")
    result = runner.invoke(repl_cli, [])
    assert result.exit_code == 0

    assert "Starting Exosphere REPL" in caplog.text


def test_ui_start(mocker, caplog) -> None:
    import logging

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)
    mock_ui = mocker.patch("exosphere.commands.ui.ExosphereUi")

    result = runner.invoke(sub_ui_cli, ["start"])

    assert result.exit_code == 0
    mock_ui.return_value.run.assert_called_once()

    assert "Starting Exosphere UI" in caplog.text


def test_ui_webstart(mocker, caplog) -> None:
    import logging

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)
    mock_server = mocker.patch("exosphere.commands.ui.Server")

    result = runner.invoke(sub_ui_cli, ["webstart"])

    assert result.exit_code == 0
    mock_server.return_value.serve.assert_called_once()

    assert "Starting Exosphere Web UI Server" in caplog.text
