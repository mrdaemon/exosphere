# Import fixtures from Fabric's suite, for general availability in tests.
# We also disable linter warnings for unused imports, since they are used elsewhere.
from fabric.testing.fixtures import connection  # noqa: F401
