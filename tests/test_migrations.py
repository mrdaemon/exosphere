"""
Tests for migrations.py

Tests for the cache file format migration functions.
Ensures backward compatibility with older cache formats, in general.
"""

from datetime import datetime, timezone

from exosphere.data import HostState, Update
from exosphere.migrations import migrate_from_host
from exosphere.objects import Host


class TestMigrations:
    """Tests for legacy Host to HostState migration"""

    def test_migrate_from_host_basic(self, mocker):
        """Test basic migration from Host to HostState"""

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.version = "12"
        host.flavor = "debian"
        host.package_manager = "apt"
        host.supported = True
        host.online = True
        host.updates = []
        host.last_refresh = None

        state = migrate_from_host(host)

        assert isinstance(state, HostState)
        assert state.os == "linux"
        assert state.version == "12"
        assert state.package_manager == "apt"
        assert state.supported is True

    def test_migrate_from_host_missing_supported(self, mocker, caplog):
        """Verify migration handles missing 'supported' attribute"""

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.online = True
        host.updates = []

        # Simulate old cache without 'supported'
        delattr(host, "supported")

        with caplog.at_level("DEBUG"):
            state = migrate_from_host(host)

        assert state.supported is True  # Default
        assert any(
            "Setting missing supported attribute to True" in message
            for message in caplog.messages
        )

    def test_migrate_from_host_converts_naive_datetime(self, mocker, caplog):
        """Verify migration converts naive datetime to UTC"""

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.supported = True
        host.online = True
        host.updates = []

        # Create naive datetime (old cache format)
        naive_dt = datetime(2026, 1, 6, 10, 30, 0)  # No timezone
        host.last_refresh = naive_dt

        with caplog.at_level("DEBUG"):
            state = migrate_from_host(host)

        # Should be converted to UTC
        assert state.last_refresh is not None
        assert state.last_refresh.tzinfo == timezone.utc
        assert any(
            "Converting timezone-naive last_refresh" in message
            for message in caplog.messages
        )

    def test_migrate_from_host_preserves_timezone_aware_datetime(self, mocker):
        """Verify migration preserves already timezone-aware datetime"""

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.supported = True
        host.online = True
        host.updates = []

        # Create timezone-aware datetime (newer cache format)
        aware_dt = datetime(2026, 1, 6, 10, 30, 0, tzinfo=timezone.utc)
        host.last_refresh = aware_dt

        state = migrate_from_host(host)

        # Should be preserved as-is
        assert state.last_refresh == aware_dt
        assert state.last_refresh is not None
        assert state.last_refresh.tzinfo == timezone.utc

    def test_migrate_from_host_with_updates(self, mocker):
        """Verify migration handles updates list"""

        host = Host(name="test_host", ip="127.0.0.1")
        host.os = "linux"
        host.supported = True
        host.online = True
        host.updates = [
            Update(
                name="libhyperoneechan",
                current_version="1.0",
                new_version="1.1",
                security=True,
            ),
        ]
        host.last_refresh = None

        state = migrate_from_host(host)

        assert isinstance(state.updates, tuple)
        assert len(state.updates) == 1
        assert state.updates[0].name == "libhyperoneechan"
