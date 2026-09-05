import tomllib
from pathlib import Path

import pytest

from exosphere import __version__, docs_url

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


class TestPackageMetadata:
    """
    Tests for package metadata exported from __init__

    These come from distinfo's *installed state*, so keep in mind the
    project needs to be synced for it to not use stale information.

    Using uv should make this a non-issue, in general.
    """

    def test_version_is_populated(self) -> None:
        """Version should resolve"""
        assert __version__

    def test_docs_url_is_absolute(self) -> None:
        """Documentation url should be an absolute https url"""
        assert docs_url.startswith("https://")

    def test_docs_url_has_no_trailing_slash(self) -> None:
        """
        Documentation url should not end in a slash
        """
        assert not docs_url.endswith("/")

    @pytest.mark.skipif(
        not PYPROJECT.is_file(), reason="pyproject.toml is not available"
    )
    def test_docs_url_matches_pyproject(self) -> None:
        """
        Documentation url should match the project.urls table
        """
        with PYPROJECT.open("rb") as f:
            expected = tomllib.load(f)["project"]["urls"]["documentation"]

        assert docs_url == expected
