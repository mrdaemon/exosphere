"""
Sphinx directives that render the release-notes index and the "What's
New?" page directly from the Markdown files under changelog/.

Each release is a ``changelog/<version>.md`` file. These directives
compute the release set at build time, so neither the ordered toctree
nor the "latest release" inline needs to be manually updated at all.

If that's not a good enough excuse to add a sixth extension to our
Sphinx bullshit, I don't know what is.

Currently implements two directives, intended to be called from Myst
Markdown:

* ``{changelog-toctree}`` — a toctree of every release, newest first
    (semver order).
* ``{changelog-latest}`` — renders the newest release inline, headings
    shifted down one level so they nest under the host page's title.
    Delegates to MyST's own ``{include}`` rather than reimplementing it
    except worse.

Dropping a ``changelog/<version>.md`` file is therefore the only manual
step needed to publish it; both pages pick it up automatically, and my
life is therefore made easier and more joyous, in spite of the ever
growing Sphinx Stockholm Syndrome.
"""

from pathlib import Path

from docutils import nodes
from docutils.statemachine import StringList
from packaging.version import InvalidVersion, Version
from sphinx.directives.other import TocTree
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

logger = logging.getLogger(__name__)


def released_versions(changelog_dir: Path) -> list[str]:
    """Return release file stems (e.g. 2.4.3), sorted newest first."""
    versions: list[str] = []

    for md in changelog_dir.glob("*.md"):
        if md.stem in ("index", "latest"):
            continue

        try:
            Version(md.stem)
        except InvalidVersion:
            logger.warning(
                "exosphere_changelog: skipping %s (filename is not a version)", md.name
            )
            continue

        versions.append(md.stem)

    return sorted(versions, key=Version, reverse=True)


class ChangelogToctree(TocTree):
    """A {toctree} of every release, newest first."""

    has_content = False

    def run(self) -> list[nodes.Node]:
        changelog_dir = Path(self.env.srcdir) / "changelog"
        versions = released_versions(changelog_dir)

        # Feed the computed entries to the stock toctree machinery.
        self.content = StringList(versions, source="<changelog-toctree>")
        self.options.setdefault("maxdepth", 1)

        return super().run()


class ChangelogLatest(SphinxDirective):
    """Render the newest release inline, under the host page's title."""

    has_content = False

    def run(self) -> list[nodes.Node]:
        changelog_dir = Path(self.env.srcdir) / "changelog"
        versions = released_versions(changelog_dir)

        if not versions:
            logger.warning(
                "exosphere_changelog: no release files found under changelog/"
            )
            return []

        # Delegate to MyST's own include (heading-offset shifts the release's
        # headings under this page's title) via a nested markdown parse.
        include = f"```{{include}} {versions[0]}.md\n:heading-offset: 1\n```"
        container = nodes.container()

        self.state.nested_parse(
            StringList(include.splitlines(), source="<changelog-latest>"),
            self.content_offset,
            container,
            match_titles=True,
        )

        return container.children


def setup(app):
    """Sphinx extension setup."""
    logger.info("Initializing exosphere_changelog extension")
    app.add_directive("changelog-toctree", ChangelogToctree)
    app.add_directive("changelog-latest", ChangelogLatest)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
