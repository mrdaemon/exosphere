import os
import sys

from exosphere import __version__

# Insert the path to the source directory to allow importing modules
sys.path.insert(0, os.path.abspath('../../src/exosphere'))

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
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_tabs.tabs',
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'renku'
html_static_path = ['_static']

# Epilog macros for documentation references
rst_epilog = """
.. |CurrentVersion| replace:: {version}
.. |CurrentVersionTag| replace:: v{version}
""".format(version=__version__)
