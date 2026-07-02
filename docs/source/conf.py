import os
import sys

from pathlib import Path

from exosphere import __version__

# Insert the path to the source directory to allow importing modules
sys.path.insert(0, os.path.abspath('../../src/exosphere'))
# Add _ext directory to path for custom extensions
sys.path.append(str(Path('_ext').resolve()))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Exosphere'
copyright = '2025, Alexandre Gauthier'
author = 'Alexandre Gauthier'
release = __version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_tabs.tabs',
    'sphinxcontrib.spelling',
    'cyclopts.sphinx_ext',
    'exosphere_lexer',  # Custom Exosphere CLI lexer
    'exosphere_help',  # Custom Exosphere CLI help SVG renderer
    'exosphere_artifacts',  # Custom extension to copy artifacts to _static
    'exosphere_cli_format',  # Custom extension to reshape CLI help summaries
    'jsonschema_doc',  # Custom extension for JSON Schema documentation
    'exosphere_changelog',  # Custom directives for release-notes index/latest pages
]

templates_path = ['_templates']

# _static holds copied/generated artifacts (see exosphere_artifacts.py)
# Now that we have a Markdown parser for release notes, those get
# unfortunately picked up as source documents, which they really aren't.
# Ignoring them here does not prevent them from being used as static
# assets for download.
exclude_patterns = ['_static/**']

# -- MyST (Markdown) configuration --------------------------------------------
# Release notes under changelog/ are authored in Markdown. Screenshots are
# committed under changelog/_assets/ and referenced as managed images, so the
# docs never depend on external (GitHub CDN) assets. linkify autolinks bare
# URLs (e.g. PyPI links) the way GitHub does.
myst_enable_extensions = [
    'linkify',
]

# Generate GitHub-style slug anchors for headings so in-page links like
# [Section](#section-title) resolve in the docs the same way they do in the
# manual GitHub release post. Depth 3 covers changelog sections even when the
# changelog-latest directive includes them with a heading offset.
myst_heading_anchors = 3

# Use a dark-friendly Pygments token palette to match dark code blocks.
pygments_style = 'nord-darker'

# -- Spell checking configuration ---------------------------------------------
# https://sphinxcontrib-spelling.readthedocs.io/en/stable/customize.html
spelling_lang = 'en_US'
spelling_word_list_filename = 'spelling_wordlist.txt'
spelling_show_suggestions = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = ['css/exosphere-overrides.css']

# Epilog macros for documentation references
rst_epilog = """
.. |CurrentVersion| replace:: {version}
.. |CurrentVersionTag| replace:: v{version}
""".format(version=__version__)
