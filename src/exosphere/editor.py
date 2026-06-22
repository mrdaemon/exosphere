"""
External editor utility module for Exosphere

Cross-platform helpers to resolve and launch the user's editor against
a file path. It should not concern itself with presentation, as it is
intended to be shared between various contexts (CLI, TUI, etc).
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Default fallback editor if none is configured or found in environment
# On Windows, this is "notepad", and everywhere else, it is "vi", as a
# last resort because surely POSIX has to at least count for something.
EDITOR_FALLBACK = "notepad" if sys.platform == "win32" else "vi"


class EditorError(Exception):
    """Base class for failures launching an external editor."""


class EditorNotFoundError(EditorError):
    """Raised when no editor could be resolved, or the resolved one is missing."""


def resolve_editor(command: str | None = None) -> list[str] | None:
    """
    Resolve the editor command to launch, as an argv list.

    Resolution order, first non-empty wins:

    1. Configuration value (the "editor" config option)
    2. The $VISUAL environment variable
    3. The $EDITOR environment variable
    4. A platform default (notepad on Windows, vi elsewhere)

    The resolved value is a command string that may carry arguments
    (e.g. "code --wait"), so it is split into argv tokens via shlex.
    The file to edit is appended separately by the caller, which avoids
    any path quoting concerns. POSIX splitting rules are used
    everywhere except Windows, where backslashes in paths would otherwise
    be mangled.

    Windows Platform Specific notes, because as always, it special:

    - Command token in config value is resolved against %PATH% via
      shutil.which so launcher wrappers or shims with non-executable
      extensions (e.g. "code.cmd") are found and run directly, because
      a bare CreateProcess does not consult PATHEXT.
    - On resolution failure, the original token is kept so the caller
      can present an error that isn't some goofy internal path.
    - Non-POSIX splitting keeps backslashes intact but it also keeps
      the surrounding quotes on a token. We therefore strip the
      matching outer pair of single or double quotes if present.
      This allows for a quoted full path with spaces to resolve, e.g.
      ``"C:\\Program Files\\TurboEdit++\\edit.exe" --wait``.
      Unquoted strings with spaces remain just as ambiguous as they
      always were, and will break as expected.

    :param command: An explicit editor command, or None to fall back to
        the environment and platform default.
    :return: The editor argv tokens, or None if nothing could be resolved.
    """
    editor = (
        command
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or EDITOR_FALLBACK
    )

    # Posix flips on Windows because backslashes and we strayed too far
    # from Pathlib's light at this point.
    argv = shlex.split(editor, posix=(os.name != "nt"))

    if not argv:
        return None

    # Non-POSIX split (Windows) keeps the surrounding quotes on a quoted
    # token, so we strip them so the path resolves.
    if os.name == "nt":
        argv = [_strip_quotes(token) for token in argv]

    resolved = shutil.which(argv[0])
    if resolved:
        argv[0] = resolved

    return argv


def _strip_quotes(token: str) -> str:
    """Strip a single matched pair of surrounding quotes from a token."""
    if len(token) < 2:
        return token

    for quote in ('"', "'"):
        if token.startswith(quote) and token.endswith(quote):
            return token[1:-1]

    return token


def open_in_editor(path: str | Path, *, editor_command: str | None = None) -> None:
    """
    Open a file in the user's editor and block until the editor exits.

    Graphical or terminal editors that launch and detach will not block
    as expected, and we make no attempt to detect or accommodate this.
    The expectation is that if your editor has a "wait" mode, it will
    be configured explicitly, e.g. "code --wait" or "subl -w", etc.

    :param path: The file to open in the editor.
    :param editor_command: An explicit editor command
    :raises EditorNotFoundError: if no editor can be resolved or launched.
    :raises EditorError: if the editor fails to launch for other reasons.
    """
    argv = resolve_editor(editor_command)

    if argv is None:
        raise EditorNotFoundError(
            "No editor could be resolved. Set the 'editor' option or the "
            "VISUAL/EDITOR environment variable."
        )

    try:
        subprocess.run([*argv, str(path)])
    except FileNotFoundError as e:
        raise EditorNotFoundError(
            f"Editor not found: {argv[0]}. Check the 'editor' option or your "
            "VISUAL/EDITOR variables."
        ) from e
    except OSError as e:
        raise EditorError(f"Failed to launch editor: {e}") from e
