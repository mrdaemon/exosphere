"""
Sphinx extension for Exosphere CLI syntax highlighting.

This extension provides a custom Pygments lexer for highlighting
Exosphere interactive CLI sessions in documentation.

It is absolutely a quick and dirty solution, but works well enough
for giving the docs a splash of color and clarity.

I can't emphasize this enough: this is gnarly.
It is also a real "What am I doing with my life?" moment.
"""

import ast
from pathlib import Path

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
    "start",
    "status",
    "sync",
    "webstart",
}


def _const_strings(value) -> list[str]:
    """Collect string constants from an AST node (a str or list/tuple of str)."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [value.value]
    if isinstance(value, (ast.List, ast.Tuple)):
        return [
            elt.value
            for elt in value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
    return []


def _extract_commands():
    """
    Extract command names from Exosphere's Cyclopts command modules.

    This function dynamically discovers:

    1. Main commands from sub apps
    2. Subcommands from @app.command decorated functions in command modules

    :return: Tuple of (main_commands_set, sub_commands_set)
    """
    main_commands = set()
    sub_commands = set()

    try:
        # Find the src directory
        src_dir = Path(__file__).parent.parent.parent.parent / "src" / "exosphere"

        commands_dir = src_dir / "commands"
        if commands_dir.exists():
            for py_file in commands_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                try:
                    content = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        # Main command name: app = App(name="...")
                        if (
                            isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Name)
                            and node.func.id == "App"
                        ):
                            for keyword in node.keywords:
                                if keyword.arg == "name":
                                    main_commands.update(_const_strings(keyword.value))

                        # Subcommands: @app.command decorators
                        if isinstance(node, ast.FunctionDef):
                            for decorator in node.decorator_list:
                                # @app.command() with arguments
                                if (
                                    isinstance(decorator, ast.Call)
                                    and isinstance(decorator.func, ast.Attribute)
                                    and isinstance(decorator.func.value, ast.Name)
                                    and decorator.func.value.id == "app"
                                    and decorator.func.attr == "command"
                                ):
                                    sub_commands.add(node.name)
                                    # Pick up synonym= aliases (str or list)
                                    for keyword in decorator.keywords:
                                        if keyword.arg == "synonym":
                                            sub_commands.update(
                                                _const_strings(keyword.value)
                                            )
                                    break
                                # @app.command without parentheses
                                elif (
                                    isinstance(decorator, ast.Attribute)
                                    and isinstance(decorator.value, ast.Name)
                                    and decorator.value.id == "app"
                                    and decorator.attr == "command"
                                ):
                                    sub_commands.add(node.name)
                                    break

                except Exception:
                    continue

    except Exception:
        # If anything goes wrong, fall back to static lists
        return _STATIC_MAIN_COMMANDS.copy(), _STATIC_SUB_COMMANDS.copy()

    # Add some common commands that might not be explicitly defined
    # (it's builtins, really)
    main_commands.update(["help", "exit", "quit"])

    return main_commands, sub_commands


# Extract commands at module level for use in class definition
_DISCOVERED_MAIN_COMMANDS, _DISCOVERED_SUB_COMMANDS = _extract_commands()

# Create patterns
_MAIN_COMMAND_PATTERN = (
    r"\b(" + "|".join(sorted(_DISCOVERED_MAIN_COMMANDS)) + r")\b"
    if _DISCOVERED_MAIN_COMMANDS
    else r"\b(" + "|".join(sorted(_STATIC_MAIN_COMMANDS)) + r")\b"
)

_SUBCOMMAND_PATTERN = (
    r"\b(" + "|".join(sorted(_DISCOVERED_SUB_COMMANDS)) + r")\b"
    if _DISCOVERED_SUB_COMMANDS
    else r"\b(" + "|".join(sorted(_STATIC_SUB_COMMANDS)) + r")\b"
)


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
    # This is useful for debugging and ensuring the lexer has the right commands
    commandslen = len(_DISCOVERED_MAIN_COMMANDS)
    subcommandslen = len(_DISCOVERED_SUB_COMMANDS)
    if commandslen or subcommandslen:
        print(
            f"[INFO] Exosphere lexer loaded with {commandslen} commands and {subcommandslen} subcommands: "
            f"Main: {sorted(_DISCOVERED_MAIN_COMMANDS)}, "
            f"Sub: {sorted(_DISCOVERED_SUB_COMMANDS)}"
        )
    else:
        print("[INFO] Exosphere lexer using fallback commands.")

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
