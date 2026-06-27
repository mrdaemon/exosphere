"""
Sphinx extension for Exosphere CLI syntax highlighting.

This extension provides a custom Pygments lexer for highlighting
Exosphere interactive CLI sessions in documentation.

It is absolutely a quick and dirty solution, but works well enough
for giving the docs a splash of color and clarity.

I can't emphasize this enough: this is gnarly.
It is also a real "What am I doing with my life?" moment.
"""

from pygments.lexer import RegexLexer
from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Whitespace,
)

# Static fallback lists of known Exosphere commands
# These lists are not intended to be maintained, but will be used if dynamic
# discovery fails or is not possible.

# Main commands
_STATIC_MAIN_COMMANDS = {
    "inventory",
    "host",
    "ui",
    "config",
    "sudo",
    "report",
    "connections",
    "version",
}

# Subcommands
_STATIC_SUB_COMMANDS = {
    "check",
    "clear",
    "close",
    "details",
    "diff",
    "discover",
    "exit",
    "generate",
    "help",
    "list",
    "paths",
    "ping",
    "policy",
    "providers",
    "quit",
    "refresh",
    "reset",
    "save",
    "show",
    "source",
    "status",
    "sync",
}


def _extract_commands():
    """
    Extract command names from Exosphere's Cyclopts application

    This function dynamically discovers:

    1. Main commands from the root app
    2. Subcommands from each of the sub-app

    Synonyms are purposefully ignored as those are only ever relevant
    within the context of the fuzzy suggestion matcher in error
    messages.

    Uses the Cyclopts API to introspect these, instead of parsing the
    AST, which the previous Typer implementation of this module did.

    :return: Tuple of (main_commands_set, sub_commands_set, used_fallback)
    """

    def _names(node) -> set[str]:
        return {name for name in node if not name.startswith("-")}

    try:
        from exosphere.cli import app

        main_commands = _names(app)
        sub_commands: set[str] = set()
        for name in main_commands:
            sub_commands |= _names(app[name])
    except Exception:
        # If the app can't be imported, fall back to static lists
        return _STATIC_MAIN_COMMANDS.copy(), _STATIC_SUB_COMMANDS.copy(), True

    # Add some common commands that might not be explicitly defined
    # (it's builtins, really)
    main_commands.update(["help", "exit", "quit"])

    return main_commands, sub_commands, False


# Extract commands at module level for use in class definition
_DISCOVERED_MAIN_COMMANDS, _DISCOVERED_SUB_COMMANDS, _USED_FALLBACK = (
    _extract_commands()
)

# Create patterns. _extract_commands always returns non-empty sets
_MAIN_COMMAND_PATTERN = r"\b(" + "|".join(sorted(_DISCOVERED_MAIN_COMMANDS)) + r")\b"
_SUBCOMMAND_PATTERN = r"\b(" + "|".join(sorted(_DISCOVERED_SUB_COMMANDS)) + r")\b"


class ExosphereLexer(RegexLexer):
    """
    A lexer for Exosphere interactive CLI sessions.

    Highlights:
    - Prompt (exosphere>)
    - Commands and subcommands (dynamically extracted from Cyclopts decorators)
    - Long options (--option)
    - Short options (-o)
    - Arguments and values
    """

    name = "Exosphere"
    aliases = ["exosphere"]
    filenames = []

    tokens = {
        "root": [
            # Prompt
            (r"^exosphere>", Generic.Prompt),
            # Comments
            (r"#.*$", Comment.Single),
            # Long options (--option, --option=value)
            (r"--[a-zA-Z0-9-]+(?:=[^\s]+)?", Name.Attribute),
            # Short options (-o, -abc)
            (r"-[a-zA-Z0-9]+", Name.Attribute),
            # Main commands (inventory, host, ui, config, sudo)
            (_MAIN_COMMAND_PATTERN, Keyword),
            # Subcommands (status, refresh, ping, etc.)
            (_SUBCOMMAND_PATTERN, Name.Builtin),
            # Generic commands (fallback for unmatched command-like words)
            (r"(?<=exosphere>)\s+([a-zA-Z][a-zA-Z0-9-_]*)", Name.Function),
            (r"(?<=\|\s)([a-zA-Z][a-zA-Z0-9-_]*)", Name.Function),
            # Quoted strings
            (r'"[^"]*"', String.Double),
            (r"'[^']*'", String.Single),
            # Numbers
            (r"\b\d+\b", Number.Integer),
            # Operators and punctuation
            (r"[|&;()<>]", Operator),
            (r"[,.]", Punctuation),
            # Host/server names (words with dots or alphanumeric with hyphens)
            (r"\b[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+\b", Name.Entity),
            (r"\b[a-zA-Z0-9-]+\b", Text),
            # Whitespace
            (r"\s+", Whitespace),
            # Everything else
            (r".", Text),
        ]
    }


def setup(app):
    from sphinx.highlighting import lexers

    # Register the Exosphere lexer
    lexers["exosphere"] = ExosphereLexer()

    # Show discovered commands in build output
    # This is useful for debugging and ensure the lexer has the right
    # commands, and what it discovered.
    # Also helps in signaling that the lexer broke and is using
    # the static fallback lists.
    if _USED_FALLBACK:
        print("[INFO] Exosphere lexer using static fallback commands.")
    else:
        print(
            f"[INFO] Exosphere lexer loaded with {len(_DISCOVERED_MAIN_COMMANDS)} commands "
            f"and {len(_DISCOVERED_SUB_COMMANDS)} subcommands: "
            f"Main: {sorted(_DISCOVERED_MAIN_COMMANDS)}, "
            f"Sub: {sorted(_DISCOVERED_SUB_COMMANDS)}"
        )

    return {
        "version": "2.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
