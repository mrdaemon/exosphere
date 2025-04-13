from typer.testing import CliRunner

from exosphere.cli import app as repl_cli
from exosphere.commands.test import app as testcommands_cli

runner = CliRunner()


def test_repl_testcommands_root() -> None:
    result = runner.invoke(repl_cli, ["test"])
    assert result.exit_code == 0


def test_testcommands_greet() -> None:
    result = runner.invoke(testcommands_cli, ["greet"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.stdout


def test_testcommands_greet_with_name() -> None:
    result = runner.invoke(testcommands_cli, ["greet", "--name", "Alice"])
    assert result.exit_code == 0
    assert "Hello, Alice!" in result.stdout


def test_testcommands_beep() -> None:
    result = runner.invoke(testcommands_cli, ["beep"])
    assert result.exit_code == 0
    assert "Beep!" in result.stdout
