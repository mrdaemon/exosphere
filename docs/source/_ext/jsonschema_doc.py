"""
A crappy Sphinx extension to generate documentation sections from
a JSON Schema file.

This was made purely because sphinx-jsonschema outputs a fat table
that barely fits in my theme layout, and felt more overwhelming
than straight up reading the json schema directly.

And so, we unfortunately now have our own shittier thing that does
tables, and arguably worse now, but it absolutely fits the layout
and context.
"""

import json
import textwrap
from pathlib import Path
from typing import List

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.util import logging

logger = logging.getLogger(__name__)


class JsonSchemaDocDirective(Directive):
    """
    Directive to generate documentation from a JSON Schema file.
    Paths are relative to **repository root** (i.e. parent of docs/),
    purely for convenience.

    Usage:
        .. jsonschema-doc:: path/to/schema.json
           :section: definitions.host
           :title: Host Object Structure
    """

    has_content = False
    required_arguments = 1  # Schema file path
    option_spec = {
        "section": str,  # Which section to document (e.g., "definitions.host")
        "title": str,  # Optional title override
    }

    def run(self) -> List[nodes.Node]:
        """Generate documentation nodes from the schema."""
        schema_path = self.arguments[0]
        section = self.options.get("section", "")
        title = self.options.get("title", "Schema Documentation")

        # Resolve schema path relative to source directory
        source_dir = Path(self.state.document.settings.env.srcdir)
        schema_file = source_dir.parent.parent / schema_path

        if not schema_file.exists():
            logger.error(f"Schema file not found: {schema_file}")
            error_node = nodes.error()
            error_node += nodes.paragraph(text=f"Schema file not found: {schema_path}")
            return [error_node]

        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)

            section_data = schema
            if section:
                for part in section.split("."):
                    section_data = section_data.get(part, {})

            return self._generate_docs(section_data, title)

        except Exception as e:
            logger.error(f"Error processing schema: {e}")
            error_node = nodes.error()
            error_node += nodes.paragraph(text=f"Error processing schema: {e}")
            return [error_node]

    def _generate_docs(self, schema_data: dict, title: str) -> List[nodes.Node]:
        """Generate documentation nodes from schema data."""
        container = nodes.container()

        # Add title
        title_para = nodes.paragraph()
        title_para += nodes.strong(text=title)
        container += title_para

        # Generate properties table
        properties = schema_data.get("properties", {})
        if properties:
            # Create table
            table = nodes.table()
            table_group = nodes.tgroup(cols=3)
            table += table_group

            # Absolutely arbitrary column width, calibrated via
            # the ancient technology of Eyeball Mk I
            table_group += nodes.colspec(colwidth=25)  # Property name
            table_group += nodes.colspec(colwidth=20)  # Type
            table_group += nodes.colspec(colwidth=55)  # Description

            # Table header
            thead = nodes.thead()
            table_group += thead
            header_row = nodes.row()
            thead += header_row

            header_row += self._make_cell("Property", is_header=True)
            header_row += self._make_cell("Type", is_header=True)
            header_row += self._make_cell("Description", is_header=True)

            # Table body
            table_body = nodes.tbody()
            table_group += table_body

            for prop_name, prop_data in properties.items():
                row = nodes.row()
                table_body += row

                # Property name (shows up in bold)
                name_cell = self._make_cell(prop_name, bold=True)
                row += name_cell

                # Type information (monospace)
                prop_type = prop_data.get("type", "unknown")
                if isinstance(prop_type, list):
                    type_str = " or ".join(prop_type)
                else:
                    type_str = prop_type

                type_cell = self._make_cell(type_str, monospace=True)
                row += type_cell

                # Description
                desc = prop_data.get("description", "No description available.")

                # Pad out description with extra metadata if available
                # (this is not exhaustive, and I BARELY care)
                constraints = []
                if "format" in prop_data:
                    constraints.append(f"Format: {prop_data['format']}")
                if "minimum" in prop_data:
                    constraints.append(f"Min: {prop_data['minimum']}")
                if "maximum" in prop_data:
                    constraints.append(f"Max: {prop_data['maximum']}")

                if constraints:
                    desc += f" ({', '.join(constraints)})"

                desc_cell = self._make_cell(desc, wrap=True)
                row += desc_cell

            container += table

        return [container]

    def _make_cell(
        self,
        text: str,
        is_header: bool = False,
        monospace: bool = False,
        wrap: bool = False,
        bold: bool = False,
    ) -> nodes.entry:
        """
        Create a table cell with the given text and formatting options.
        Also handles magic line-wrapping for long fields and formatting
        of table headers, etc.
        """
        cell = nodes.entry()

        # Wrap to arbitrary width of 50 characters, if requested
        # This ensures the description field is not awful
        if wrap and len(text) > 50:
            wrapped_lines = textwrap.wrap(text, width=50)
            for line in wrapped_lines:
                paragraph_output = nodes.paragraph()
                paragraph_output += (
                    nodes.Text(line) if not bold else nodes.strong(text=line)
                )
                cell += paragraph_output
        else:
            paragraph_output = nodes.paragraph()
            if is_header:
                paragraph_output += nodes.strong(text=text)
            elif monospace:
                paragraph_output += nodes.literal(text=text)
            elif bold:
                paragraph_output += nodes.strong(text=text)
            else:
                paragraph_output += nodes.Text(text)
            cell += paragraph_output

        return cell


def setup(app):
    """Sphinx extension setup."""
    logger.info("Initializing internal jsonschema_doc extension")
    app.add_directive("jsonschema-doc", JsonSchemaDocDirective)

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
