import pytest

from exosphere.database import DiskCache


@pytest.fixture
def tmp_db(tmp_path):
    path = tmp_path / "testdb.db"
    yield str(path)


def test_set_and_get_item(tmp_db):
    """
    Test setting and getting an item with DiskCache
    """
    with DiskCache(tmp_db) as cache:
        cache["foo"] = {"bar": 42}
        assert cache["foo"] == {"bar": 42}


def test_overwrite_item(tmp_db):
    """
    Test overwriting an item in DiskCache
    """
    with DiskCache(tmp_db) as cache:
        cache["key"] = 1
        cache["key"] = 2
        assert cache["key"] == 2


def test_get_method_existing_key(tmp_db):
    """
    Test the get method with an existing key
    """
    with DiskCache(tmp_db) as cache:
        cache["a"] = "b"
        assert cache.get("a") == "b"


def test_get_method_missing_key_returns_default(tmp_db):
    """
    Test the get method with a missing key, should return default value
    """
    with DiskCache(tmp_db) as cache:
        assert cache.get("missing", 123) == 123


def test_key_error_on_missing_key(tmp_db):
    """
    Test that accessing a missing key raises KeyError
    """
    with DiskCache(tmp_db) as cache:
        with pytest.raises(KeyError):
            _ = cache["notfound"]


@pytest.mark.parametrize(
    "value",
    [
        123,
        45.6,
        "string",
        [1, 2, 3],
        {"x": 1, "y": [2, 3]},
        (1, 2),
        None,
        True,
    ],
    ids=["integer", "float", "string", "list", "dict", "tuple", "none", "boolean"],
)
def test_various_data_types(tmp_db, value):
    """
    Test storing and retrieving various data types in DiskCache
    """
    with DiskCache(tmp_db) as cache:
        cache["key"] = value
        assert cache["key"] == value
