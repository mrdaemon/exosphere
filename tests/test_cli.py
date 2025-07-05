from typer.testing import CliRunner

runner = CliRunner()


def test_win32readline_monkeypatch(monkeypatch, mocker) -> None:
    """
    Test that the windows compatibility shim for pyreadline is
    correctly applied when running on Windows.
    """
    import importlib
    import sys
    import types

    # fake sys.platform to be win32
    monkeypatch.setattr(sys, "platform", "win32")

    # Mock the compatibility module
    compat_shim = types.ModuleType("exosphere.compat.win32readline")
    monkeypatch.setitem(sys.modules, "exosphere.compat.win32readline", compat_shim)

    import exosphere.compat

    setattr(exosphere.compat, "win32readline", compat_shim)

    # Clean modules to ensure proper imports
    sys.modules.pop("readline", None)
    sys.modules.pop("exosphere.cli", None)

    # Reimport the cli module to trigger the monkeypatch
    # but patch out codepaths with win32 specific imports.
    # This is untenable long-term, and this test needs refactored.
    mocker.patch("ssl.create_default_context")

    import exosphere.cli  # noqa: F401

    importlib.reload(exosphere.cli)

    # Ensure the compatibility shim is used
    assert "readline" in sys.modules
    assert sys.modules["readline"] is compat_shim


def test_repl_root(mocker, caplog) -> None:
    import logging

    from exosphere.cli import app as repl_cli

    logging.getLogger("exosphere.cli").setLevel(logging.INFO)
    logging.getLogger("exopshere.cli").addHandler(caplog.handler)

    mocker.patch("exosphere.cli.make_click_shell")
    result = runner.invoke(repl_cli, [])
    assert result.exit_code == 0

    assert "Starting Exosphere REPL" in caplog.text


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


def test_ui_webstart(mocker, caplog) -> None:
    import logging

    from exosphere.commands.ui import app as sub_ui_cli

    logging.getLogger("exosphere.commands.ui").setLevel(logging.INFO)
    logging.getLogger("exopshere.commands.ui").addHandler(caplog.handler)
    mock_server = mocker.patch("exosphere.commands.ui.Server")

    result = runner.invoke(sub_ui_cli, ["webstart"])

    assert result.exit_code == 0
    mock_server.return_value.serve.assert_called_once()

    assert "Starting Exosphere Web UI Server" in caplog.text


def test_help_no_command(mocker):
    """
    Test the 'help' command with no arguments.
    Should make use of our internal help override
    """
    from exosphere.cli import app as repl_cli

    # Patch Panel.fit to just return its content for easier assertion
    mocker.patch("rich.panel.Panel.fit", side_effect=lambda content, **kwargs: content)
    result = runner.invoke(repl_cli, ["help"])
    assert result.exit_code == 0

    # Should mention available modules and help usage
    assert "Available modules during interactive use" in result.output
    assert "Use '<command> --help'" in result.output


def test_help_command(mocker):
    """
    Test the 'help' command with a specific subcommand.
    Should print the help text for that command.
    """
    from exosphere.cli import app as repl_cli

    # Patch Panel.fit to just return its content for easier assertion
    mocker.patch("rich.panel.Panel.fit", side_effect=lambda content, **kwargs: content)

    result = runner.invoke(repl_cli, ["help", "config"])
    assert result.exit_code == 0

    # Should mention the help text for the 'config' command
    assert "Runtime Configuration Commands" in result.output


def test_help_unknown_command(monkeypatch):
    """
    Test the 'help' command with an unknown subcommand.
    Should print an error message.
    """
    from exosphere.cli import app as repl_cli

    result = runner.invoke(repl_cli, ["help", "doesnotexist"])
    assert result.exit_code == 0
    assert "Unkown command 'doesnotexist'" in result.output
    assert "Use '<command> --help'" in result.output
