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

# We only apply this dirty hack to the command reference section
TARGET_DOCNAME = "command_reference"

# Prefixes for anchors, internal and external
CYCLOPTS_ANCHOR_PREFIX = "cyclopts-"
PUBLIC_ANCHOR_PREFIX = "exosphere-"

# Class tagged on subcommand sections
# Helper intended purely to lubricatre CSS styling
SUBCOMMAND_SECTION_CLASS = "exosphere-subcommand"


def _first_paragraph(section):
    """Return the first direct-child paragraph of a section, or None."""
    return next((c for c in section.children if isinstance(c, nodes.paragraph)), None)


def tag_subcommand_sections(app, doctree):
    """
    Tag a class on every subcommand section, purely as a CSS hook.

    See exosphere-overrides.css for details, but the gist of it is
    that we want to format the subcommands slightly differently, and
    this is the path of least resistance to being able to distinguish
    them.
    """
    if app.env.docname != TARGET_DOCNAME:
        return

    for section in doctree.findall(nodes.section):
        if any(isinstance(child, nodes.literal_block) for child in section.children):
            section["classes"].append(SUBCOMMAND_SECTION_CLASS)


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


def namespace_command_anchors(app, doctree):
    """
    Make the namespaced anchor the primary id of each command section.

    Sucommand names can clash across commands (i.e. inventory discover
    vs host discover, anything with 'show' etc). As a result the
    stupid toctree will contain a bunch of anchor links within sections
    all claiming '#discover' or '#show' for themselves and every link
    will land on whichever sorted first in the document, which is not
    desirable in any way shape or form.

    Cyclopts already has a unique ``.. _cyclopts-<group>-<command>:``
    label for each command, so the section carries a perfectly good
    namespaced id as well, it's just, infuriatingly, not the one
    being used:

        ids = ["discover", "cyclopts-inventory-discover"]

    So this function just promotes the namespaced id to the top while
    renaming the prefix so it doesn't look ass in user facing links, and
    drops the bare one, which fixes the navigation, gets rid of
    duplicate id attributes in the output, solves world hunger and
    waters my plants.

    We also keep the original id as a secondary anchor on purpose to
    name the sections and honor ``:ref:`` links, if any.

    This should run *before* the toctree collector, to ensure it
    happens before the ids are picked up, and should be connected in
    setup() with a priority of 400, otherwise it won't be effective.
    """
    if app.env.docname != TARGET_DOCNAME:
        return

    for section in doctree.findall(nodes.section):
        ids = section["ids"]

        qualified = next((i for i in ids if i.startswith(CYCLOPTS_ANCHOR_PREFIX)), None)

        if qualified is None:
            continue

        public = PUBLIC_ANCHOR_PREFIX + qualified.removeprefix(CYCLOPTS_ANCHOR_PREFIX)

        if ids[0] == public:
            continue

        # A good traditional dirty print for useful output during build
        print(f"Renaming command anchor {ids[0]} -> {public} in {TARGET_DOCNAME}")

        section["ids"] = [public, qualified]

        # Keep docutils' id bookkeeping aware of the anchor we just
        # invented, so nothing else can lay claim to it later on.
        # It's also good form, and polite. Probably.
        doctree.ids.setdefault(public, section)


def setup(app):
    print("[INFO] Exosphere CLI Help Hack extension loaded")

    app.connect("doctree-read", namespace_command_anchors, priority=400)
    app.connect("doctree-read", promote_command_summaries)
    app.connect("doctree-read", tag_subcommand_sections)

    return {"parallel_read_safe": True, "parallel_write_safe": True}
