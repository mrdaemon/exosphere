"""
Shitty Sphinx extensions to promote CLI command summaries

This is incredibly specific to the Exosphere Documentation, and mainly
exists because the cyclopts extension doesn't provide a clean way to do
this out of the box, and the options were:

* Wrapping the extension in a custom directive (no, we have enough)
* CSS styling (no, fragile, and the grossest)
* Monkey-patching the cyclopts extension (no, too fragile and hacky)
* Manipulating the doctree after it's been built

So we do the last one, which is still gross, and hacky, but also
required the least amount of effort, and can absolutely be scoped
exclusively to the "command reference" section.
"""

from docutils import nodes
from sphinx.util import logging

logger = logging.getLogger(__name__)

# We only apply this dirty hack to the command reference section
TARGET_DOCNAME = "command_reference"


def _first_paragraph(section):
    """Return the first direct-child paragraph of a section, or None."""
    return next(
        (c for c in section.children if isinstance(c, nodes.paragraph)), None
    )


def promote_command_summaries(app, doctree):
    """
    Move the first line of command docstrings (summary) to sit
    immediately after the section title, and make it bold as a
    pseudo-subheading, which vastly improves readability, IMO.

    The hacky way sections are identified is by looking for a usage
    litera_block in its direct children, which our hand-written headings
    do not currently have.

    The top level group sections are also bolded in place (but not
    moved, there's no need to).

    This is gross and hacky, but works.
    """
    if app.env.docname != TARGET_DOCNAME:
        return

    for section in doctree.findall(nodes.section):
        if not any(
            isinstance(child, nodes.literal_block) for child in section.children
        ):
            continue

        summary = _first_paragraph(section)
        if summary is None:
            continue

        summary.children = [nodes.strong("", "", *summary.children)]

        # Move the summary to just after the title (which is always first).
        section.remove(summary)
        section.insert(1, summary)

    # Bold the module-help summary of each top-level group, in place.
    for section in doctree.findall(nodes.section):
        if any(isinstance(c, nodes.literal_block) for c in section.children):
            continue  # a command section, already handled above

        has_command_child = any(
            any(isinstance(gc, nodes.literal_block) for gc in child.children)
            for child in section.children
            if isinstance(child, nodes.section)
        )

        if not has_command_child:
            continue

        summary = _first_paragraph(section)
        if summary is None:
            continue

        summary.children = [nodes.strong("", "", *summary.children)]


def setup(app):
    print("[INFO] Exosphere CLI Help Hack extension loaded")

    app.connect("doctree-read", promote_command_summaries)

    return {"parallel_read_safe": True, "parallel_write_safe": True}
