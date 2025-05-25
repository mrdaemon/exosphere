from typer.testing import CliRunner

from exosphere.cli import app as repl_cli
from exosphere.commands.test import app as sub_test_cli
from exosphere.commands.ui import app as sub_ui_cli

runner = CliRunner()


def test_repl_testcommands_root() -> None:
    result = runner.invoke(repl_cli, ["test"])
    assert result.exit_code == 0


def test_testcommands_greet() -> None:
    result = runner.invoke(sub_test_cli, ["greet"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_testcommands_greet_with_name() -> None:
    result = runner.invoke(sub_test_cli, ["greet", "--name", "Alice"])
    assert result.exit_code == 0
    assert "Hello, Alice!" in result.stdout


def test_testcommands_beep() -> None:
    result = runner.invoke(sub_test_cli, ["beep"])
    assert result.exit_code == 0
    assert "Beep!" in result.stdout


def test_ui_start(mocker, caplog) -> None:
    import logging

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)
    mock_ui = mocker.patch("exosphere.commands.ui.ExosphereUi")

    result = runner.invoke(sub_ui_cli)

    print(result.output)

    assert result.exit_code == 0
    mock_ui.return_value.run.assert_called_once()

    assert "Starting Exosphere UI" in caplog.text
