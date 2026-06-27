import logging

import pytest
from cyclopts import Group

from exosphere import __version__, cli
from exosphere.config import Configuration


@pytest.fixture(autouse=True)
def _console(patch_console):
    """Deterministic console for CLI tests."""
    patch_console(cli)


def test_subapps_share_root_help_formatter() -> None:
    """Every group sub-app shares the root's help_formatter."""
    from exosphere import cli

    root_formatter = cli.app.help_formatter
    assert root_formatter is not None

    names = [name for name in cli.app if not name.startswith("-")]
    assert names  # sanity: sub-apps are registered

    for name in names:
        assert cli.app[name].help_formatter is root_formatter, name


def test_root_help_version_grouped_as_parameters() -> None:
    """The flags should not be in "Commands", like Typer"""
    from exosphere import cli

    for flag in ("--help", "--version"):
        group = cli.app[flag].group
        assert isinstance(group, tuple)
        assert any(isinstance(g, Group) and g.name == "Parameters" for g in group), flag


def test_repl_root(mocker, caplog, capsys) -> None:
    """Interactive entrypoint prints the banner and starts the REPL."""
    from exosphere import cli

    caplog.set_level(logging.INFO, logger="exosphere.cli")
    mock_repl = mocker.patch("exosphere.cli.start_repl")

    cli.start_interactive()

    mock_repl.assert_called_once()
    assert "Starting Exosphere REPL" in caplog.text
    assert f"v{__version__}" in capsys.readouterr().out


def test_repl_root_no_banner(mocker, capsys) -> None:
    """Interactive entrypoint omits the banner when disabled."""
    from exosphere import cli

    # Prepare configuration with no_banner set to True
    config = Configuration()
    config.update_from_mapping({"options": {"no_banner": True}})
    mocker.patch("exosphere.cli.app_config", config)

    mock_repl = mocker.patch("exosphere.cli.start_repl")

    cli.start_interactive()

    mock_repl.assert_called_once()
    assert f"v{__version__}" not in capsys.readouterr().out


def test_repl_version(capsys) -> None:
    """
    --version prints the version of Exosphere.

    Should be handled by Cyclopts, but the string should be stable
    """
    from exosphere import cli

    with pytest.raises(SystemExit) as exc_info:
        cli.app(["--version"])

    assert exc_info.value.code == 0
    assert "Exosphere version" in capsys.readouterr().out


def test_unused_tokens_error_is_reworded(capsys) -> None:
    """Extraneous arguments produce our friendlier error, not Cyclopts' raw dump."""
    from exosphere import cli

    with pytest.raises(SystemExit) as exc_info:
        cli.app(["version", "stray"])

    assert exc_info.value.code == 1

    err = capsys.readouterr().err
    assert "Unexpected argument(s): stray. See --help for usage." in err
    assert "Unused Tokens" not in err


def test_ui(mocker, caplog) -> None:
    """UI entrypoint starts the UI"""
    from exosphere.commands import ui

    caplog.set_level(logging.INFO, logger="exosphere.commands.ui")
    mock_ui = mocker.patch("exosphere.commands.ui.ExosphereUi")

    code = ui.app([], result_action="return_value")

    assert code is None
    mock_ui.return_value.run.assert_called_once()
    assert "Starting Exosphere UI" in caplog.text


def test_ui_start_compat(mocker) -> None:
    """UI entrypoint accepts 'start' as argument for compatibility."""
    from exosphere.commands import ui

    mock_ui = mocker.patch("exosphere.commands.ui.ExosphereUi")

    code = ui.app(["start"], result_action="return_value")

    assert code is None
    mock_ui.return_value.run.assert_called_once()
