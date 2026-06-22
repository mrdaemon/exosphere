import pytest

from exosphere import editor
from exosphere.editor import EditorError, EditorNotFoundError


class TestResolveEditor:
    """Tests for editor.resolve_editor."""

    @pytest.fixture(autouse=True)
    def _no_path_resolution(self, mocker):
        """
        Default to no PATH resolution so the resolution-order tests assert on
        the chosen command string, independent of what is installed locally.
        """
        return mocker.patch("exosphere.editor.shutil.which", return_value=None)

    def test_resolves_executable_on_path(self, mocker):
        """The executable token is replaced with its resolved PATH location."""
        mocker.patch(
            "exosphere.editor.shutil.which",
            return_value=r"C:\tools\code.CMD",
        )

        assert editor.resolve_editor("code --wait") == [r"C:\tools\code.CMD", "--wait"]

    def test_configured_wins(self, monkeypatch):
        """The configured value takes precedence over the environment."""
        monkeypatch.setenv("VISUAL", "vis")
        monkeypatch.setenv("EDITOR", "ed")

        assert editor.resolve_editor("myeditor --wait") == ["myeditor", "--wait"]

    def test_visual_env(self, monkeypatch):
        """VISUAL is used when nothing is configured, over EDITOR."""
        monkeypatch.setenv("VISUAL", "vis")
        monkeypatch.setenv("EDITOR", "ed")

        assert editor.resolve_editor() == ["vis"]

    def test_editor_env(self, monkeypatch):
        """EDITOR is used when nothing is configured and VISUAL is unset."""
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "ed")

        assert editor.resolve_editor() == ["ed"]

    def test_platform_fallback(self, monkeypatch):
        """The platform fallback is used when nothing else is set."""
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)

        assert editor.resolve_editor() == [editor.EDITOR_FALLBACK]

    def test_windows_unquotes_quoted_path(self, mocker, monkeypatch):
        """On Windows, a double-quoted path with spaces is unquoted and resolved."""
        monkeypatch.setattr(editor.os, "name", "nt")
        mocker.patch(
            "exosphere.editor.shutil.which",
            return_value=r"C:\Program Files\TurboEdit++\edit.exe",
        )

        argv = editor.resolve_editor(r'"C:\Program Files\TurboEdit++\edit.exe" --wait')

        assert argv == [r"C:\Program Files\TurboEdit++\edit.exe", "--wait"]

    def test_windows_unquotes_single_quoted_path(self, monkeypatch):
        """On Windows, a single-quoted path is also unquoted."""
        monkeypatch.setattr(editor.os, "name", "nt")

        # autouse fixture leaves shutil.which -> None.
        # Token is kept as-is.

        argv = editor.resolve_editor(r"'C:\Tools\ed.exe' --wait")

        assert argv == [r"C:\Tools\ed.exe", "--wait"]

    def test_windows_preserves_unquoted_backslash_path(self, monkeypatch):
        """On Windows, backslashes in an unquoted (space-free) path survive."""
        monkeypatch.setattr(editor.os, "name", "nt")

        argv = editor.resolve_editor(r"C:\Tools\ed.exe --wait")

        assert argv == [r"C:\Tools\ed.exe", "--wait"]


class TestOpenInEditor:
    """Tests for editor.open_in_editor."""

    def test_launches_editor_with_path(self, mocker, monkeypatch):
        """The resolved editor is run against the given path."""
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        mocker.patch("exosphere.editor.shutil.which", return_value=None)
        run = mocker.patch("exosphere.editor.subprocess.run")

        editor.open_in_editor("/tmp/config.yaml", editor_command="myeditor")

        run.assert_called_once_with(["myeditor", "/tmp/config.yaml"])

    def test_no_editor_raises(self, mocker):
        """When nothing resolves, EditorNotFoundError is raised."""
        mocker.patch("exosphere.editor.resolve_editor", return_value=None)
        run = mocker.patch("exosphere.editor.subprocess.run")

        with pytest.raises(EditorNotFoundError, match="No editor could be resolved"):
            editor.open_in_editor("/tmp/config.yaml")

        assert not run.called

    def test_missing_binary_raises_not_found(self, mocker):
        """A FileNotFoundError from the launch maps to EditorNotFoundError."""
        mocker.patch("exosphere.editor.resolve_editor", return_value=["nope"])
        mocker.patch("exosphere.editor.subprocess.run", side_effect=FileNotFoundError())

        with pytest.raises(EditorNotFoundError, match="Editor not found: nope"):
            editor.open_in_editor("/tmp/config.yaml")

    def test_other_oserror_raises_editor_error(self, mocker):
        """A generic OSError from the launch maps to EditorError."""
        mocker.patch("exosphere.editor.resolve_editor", return_value=["myeditor"])
        mocker.patch(
            "exosphere.editor.subprocess.run",
            side_effect=OSError("boom"),
        )

        with pytest.raises(EditorError, match="Failed to launch editor"):
            editor.open_in_editor("/tmp/config.yaml")
