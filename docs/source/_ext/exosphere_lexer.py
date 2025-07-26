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

# Static fallback list of known Exosphere commands
# This list is not intended to be maintained, but will be used if dynamic
# discovery fails or is not possible.
_STATIC_COMMANDS = {
    "check",
    "clear",
    "diff",
    "discover",
    "exit",
    "generate",
    "help",
    "paths",
    "ping",
    "policy",
    "providers",
    "quit",
    "refresh",
    "save",
    "show",
    "source",
    "start",
    "status",
    "webstart",
}


def _extract_typer_commands():
    """
    Extract command names from Exosphere's Typer command modules.

    This function dynamically discovers all @app.command() decorated functions
    in the exosphere.commands.* modules and returns their names for use in
    syntax highlighting.

    Returns:
        set: A set of command names found in the Typer modules
    """
    commands = set()

    try:
        # Try to find the commands directory relative to the docs
        commands_dir = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "exosphere"
            / "commands"
        )

        if not commands_dir.exists():
            # Fallback to static list if we can't find the commands
            return _STATIC_COMMANDS.copy()

        # Parse each Python file in the commands directory
        for py_file in commands_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse the AST to find @app.command() decorators
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Look for function definitions with @app.command() decorator
                    if isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            # Check if it's @app.command()
                            if (
                                isinstance(decorator, ast.Call)
                                and isinstance(decorator.func, ast.Attribute)
                                and isinstance(decorator.func.value, ast.Name)
                                and decorator.func.value.id == "app"
                                and decorator.func.attr == "command"
                            ):
                                commands.add(node.name)
                                break
                            # Also check for @app.command without parentheses
                            elif (
                                isinstance(decorator, ast.Attribute)
                                and isinstance(decorator.value, ast.Name)
                                and decorator.value.id == "app"
                                and decorator.attr == "command"
                            ):
                                commands.add(node.name)
                                break

            except Exception:
                # If we can't parse a file, skip it
                continue

    except Exception:
        # If anything goes wrong, fall back to static list
        return _STATIC_COMMANDS.copy()

    # Add some common commands that might not be in modules
    commands.update(["help", "exit", "quit"])

    return commands


# Extract commands at module level for use in class definition
_DISCOVERED_COMMANDS = _extract_typer_commands()
_SUBCOMMAND_PATTERN = (
    r"\b(" + "|".join(sorted(_DISCOVERED_COMMANDS)) + r")\b"
    if _DISCOVERED_COMMANDS
    else r"\b(" + "|".join(sorted(_STATIC_COMMANDS)) + r")\b"
)


class ExosphereLexer(RegexLexer):
    """
    A lexer for Exosphere interactive CLI sessions.

    Highlights:
    - Prompt (exosphere>)
    - Commands and subcommands (dynamically extracted from Typer decorators)
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
            # Commands (first word after prompt or after pipe)
            (r"(?<=exosphere>)\s+([a-zA-Z][a-zA-Z0-9-_]*)", Name.Builtin),
            (r"(?<=\|\s)([a-zA-Z][a-zA-Z0-9-_]*)", Name.Builtin),
            # Subcommands (dynamically extracted from Typer decorators)
            (_SUBCOMMAND_PATTERN, Keyword),
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
    if _DISCOVERED_COMMANDS:
        print(
            f"[INFO] Exosphere lexer loaded with {len(_DISCOVERED_COMMANDS)} commands:"
            f" {sorted(_DISCOVERED_COMMANDS)}"
        )
    else:
        print("[INFO] Exosphere lexer loaded with static fallback commands")

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
