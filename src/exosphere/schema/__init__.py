"""
JSON Schema definitions for Exosphere data structures.

Currently only supports the host report schema, which is only
ever used for validating output in the test suite.
"""

import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent


def load_schema(name: str) -> dict:
    """
    Load a JSON schema by name

    :param name: Schema name (without .json extension)
    :return: Parsed JSON schema
    """
    schema_path = SCHEMA_DIR / f"{name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_host_report_schema() -> dict:
    """Get the host report JSON schema."""
    return load_schema("host-report")
