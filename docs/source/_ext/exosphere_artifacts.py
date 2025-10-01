"""
Sphinx extension as a dirty hack to copy artifacts into source _static
at buildtime, to make them available for download or reference directly
in the documentation.

This is incredibly internal and of no use to anyone other than as maybe
as a bad example, or as reference in a study on how people who can't
figure out how to work Sphinx to achieve what they want just hack some
shitty Python together to muddle through.
"""

import shutil
from pathlib import Path

from sphinx.util import logging

logger = logging.getLogger(__name__)


def copy_artifacts(app):
    """
    Copy necessary artifacts into the source _static directory.
    Only copy if source is newer than destination to avoid autobuild loops.
    """

    # List of artifacts to copy: (source_path, destination_filename)
    # NOTE: Don't forget to add new artifacts to .gitignore if needed
    artifacts = [
        ("src/exosphere/schema/host-report.schema.json", "host-report.schema.json"),
        # Report examples for documentation
        ("examples/reports/full.html", "reports/full.html"),
        ("examples/reports/full.txt", "reports/full.txt"),
        ("examples/reports/full.md", "reports/full.md"),
        ("examples/reports/full.json", "reports/full.json"),
        ("examples/reports/securityonly.html", "reports/securityonly.html"),
        ("examples/reports/securityonly.txt", "reports/securityonly.txt"),
        ("examples/reports/securityonly.md", "reports/securityonly.md"),
        ("examples/reports/securityonly.json", "reports/securityonly.json"),
        ("examples/reports/updatesonly.html", "reports/updatesonly.html"),
        ("examples/reports/updatesonly.txt", "reports/updatesonly.txt"),
        ("examples/reports/updatesonly.md", "reports/updatesonly.md"),
        ("examples/reports/updatesonly.json", "reports/updatesonly.json"),
        ("examples/reports/filtered.html", "reports/filtered.html"),
        ("examples/reports/filtered.txt", "reports/filtered.txt"),
        ("examples/reports/filtered.md", "reports/filtered.md"),
        ("examples/reports/filtered.json", "reports/filtered.json"),
        ("examples/reports/full-no-navigation.html", "reports/full-no-navigation.html"),
    ]

    # Destination directory in source _static
    static_source_dir = Path(app.srcdir) / "_static"
    static_source_dir.mkdir(exist_ok=True)

    # Create reports subdirectory
    reports_dir = static_source_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Copy each artifact only if needed
    for source_path, dest_filename in artifacts:
        # Resolve source path relative to project root (parent of docs/)
        source_file = Path(app.confdir).parent.parent / source_path
        dest_file = static_source_dir / dest_filename

        if not source_file.exists():
            logger.error(f"Artifact source not found: {source_file}")
            continue

        # Only copy if destination doesn't exist or source is newer
        should_copy = (
            not dest_file.exists()
            or source_file.stat().st_mtime > dest_file.stat().st_mtime
        )

        if should_copy:
            shutil.copy2(source_file, dest_file)
            logger.info(f"Copied artifact: {source_file} -> {dest_file}")
        else:
            logger.info(f"Artifact up to date: {dest_filename}")


def setup(app):
    """Sphinx extension setup."""
    logger.info("Initializing exosphere_artifacts extension")
    app.connect("builder-inited", copy_artifacts)
