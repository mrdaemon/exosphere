from pathlib import Path

from exosphere import fspaths


def test_get_dirs_returns_expected_keys():
    """
    Test that the directory paths returned by get_dirs() are as expected.
    """
    dirs = fspaths.get_dirs()
    assert set(dirs.keys()) == {"config", "state", "log", "cache"}
    for v in dirs.values():
        assert isinstance(v, str)
        assert v  # Should not be empty


def test_dirs_are_pathlike():
    """
    Supremely low quality test to ensure that we get Path-like objects
    """
    assert isinstance(fspaths.CONFIG_DIR, Path)
    assert isinstance(fspaths.STATE_DIR, Path)
    assert isinstance(fspaths.LOG_DIR, Path)
    assert isinstance(fspaths.CACHE_DIR, Path)


def test_ensure_dirs_creates_directories(mocker):
    """
    Test that ensure_dirs() creates the expected directories.
    """
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")
    fspaths.ensure_dirs()
    assert mock_mkdir.call_count == 4
    for call in mock_mkdir.call_args_list:
        assert call.kwargs["parents"] is True
        assert call.kwargs["exist_ok"] is True
