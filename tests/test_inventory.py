from unittest import mock

import pytest

from exosphere.config import Configuration
from exosphere.data import HostState
from exosphere.inventory import FilterMode, Inventory, SortField
from exosphere.objects import Host, HostOperation
from exosphere.security import SudoPolicy


class TestSortField:
    """
    Tests for the SortField enum.

    Since it is a hacky Enum with custom attributes and a constructor,
    we ensure the basic enum properties hold, and we have not broken
    anything fundamental to its behavior, or within our custom uses.
    """

    @pytest.mark.parametrize("field", list(SortField))
    def test_value_is_nonempty_string_token(self, field):
        assert isinstance(field.value, str) and field.value

    @pytest.mark.parametrize("field", list(SortField))
    def test_has_label(self, field):
        assert isinstance(field.label, str) and field.label

    @pytest.mark.parametrize("field", list(SortField))
    def test_key_and_has_value_are_callable(self, field):
        """Test that each field has a sort key and has_value function."""
        assert callable(field.key)
        assert callable(field.has_value)

    @pytest.mark.parametrize("field", list(SortField))
    def test_reverse_lookup_by_value(self, field):
        assert SortField(field.value) is field


class TestInventory:
    @pytest.fixture
    def mock_config(self):
        data = {
            "options": {"cache_file": "test_cache.db"},
            "hosts": [
                {"name": "host1", "ip": "127.0.0.1", "port": 22},
                {"name": "host2", "ip": "127.0.0.2", "port": 22},
                {
                    "name": "host3",
                    "ip": "127.0.0.3",
                    "description": "Test host",
                    "port": 2222,
                },
                {"name": "host4", "ip": "127.0.0.4", "username": "test_user"},
                {"name": "host5", "ip": "127.0.0.5", "sudo_policy": "nopasswd"},
            ],
        }
        config = Configuration()
        config.update_from_mapping(data)
        return config

    @pytest.fixture(autouse=True)
    def mock_diskcache(self, mocker):
        # We should never write to the actual disk cache during tests.
        mock_dc = mocker.patch("exosphere.inventory.DiskCache")
        return mock_dc

    @staticmethod
    def _mkhost(
        mocker,
        name,
        os: str | None = "linux",
        flavor=None,
        version=None,
        updates=0,
        security=0,
        online=True,
        supported=True,
    ):
        """
        Create a lightweight mock Host for filter/sort tests.

        Hosts default to a discovered state.
        Pass ``os=None`` to mock an undiscovered host.
        """
        host = mocker.Mock(spec=Host)
        host.name = name
        host.os = os
        host.flavor = flavor
        host.version = version
        host.online = online
        host.supported = supported
        host.updates = [mocker.Mock() for _ in range(updates)]
        host.security_updates = [mocker.Mock() for _ in range(security)]
        return host

    @pytest.fixture
    def view_inventory(self, mock_config, mocker):
        """
        An inventory with crafted hosts for filter/sort tests.

        They all have predictable names (nato phonetic) and varying
        attributes, and one (delta) is an unsupported host: it reports
        an OS but no flavor/version.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(
                mocker,
                "alpha",
                os="linux",
                flavor="debian",
                version="12",
                updates=3,
                security=1,
                online=True,
            ),
            self._mkhost(
                mocker,
                "bravo",
                os="linux",
                flavor="debian",
                version="9",
                updates=0,
                security=0,
                online=True,
            ),
            self._mkhost(
                mocker,
                "charlie",
                os="freebsd",
                flavor="freebsd",
                version="14.0",
                updates=5,
                security=2,
                online=False,
            ),
            self._mkhost(
                mocker,
                "delta",
                os="plan9",
                flavor=None,
                version=None,
                updates=0,
                security=0,
                online=False,
                supported=False,
            ),
        ]
        return inventory

    def test_init_all(self, mock_config):
        """
        Test that init_all creates Host objects from the configuration.
        """
        inventory = Inventory(mock_config)

        assert len(inventory.hosts) == 5

        assert inventory.hosts[0].name == "host1"
        assert inventory.hosts[0].ip == "127.0.0.1"
        assert inventory.hosts[0].port == 22
        assert inventory.hosts[0].username is None
        assert inventory.hosts[0].description is None

        assert inventory.hosts[1].name == "host2"
        assert inventory.hosts[1].ip == "127.0.0.2"
        assert inventory.hosts[1].port == 22
        assert inventory.hosts[1].username is None
        assert inventory.hosts[1].description is None

        assert inventory.hosts[2].name == "host3"
        assert inventory.hosts[2].ip == "127.0.0.3"
        assert inventory.hosts[2].description == "Test host"
        assert inventory.hosts[2].port == 2222
        assert inventory.hosts[2].username is None

        assert inventory.hosts[3].name == "host4"
        assert inventory.hosts[3].ip == "127.0.0.4"
        assert inventory.hosts[3].username == "test_user"
        assert inventory.hosts[3].description is None
        assert inventory.hosts[3].port == 22

        assert inventory.hosts[4].name == "host5"
        assert inventory.hosts[4].ip == "127.0.0.5"
        assert inventory.hosts[4].sudo_policy == SudoPolicy.NOPASSWD

    def test_init_all_with_empty_hosts(self, caplog):
        """
        Test that init_all handles empty host configuration gracefully.
        """
        config_data = {
            "options": {"cache_file": "test_cache.db"},
            "hosts": [],  # Empty hosts
        }
        config = Configuration()
        config.update_from_mapping(config_data)

        with caplog.at_level("WARNING"):
            inventory = Inventory(config)

        assert len(inventory.hosts) == 0
        assert any("No hosts found in inventory" in m for m in caplog.messages)

    @pytest.mark.parametrize(
        "cache_autopurge,cache_autosave,expected_purge",
        [
            (True, True, True),
            (False, True, False),
            (True, False, False),
            (False, False, False),
        ],
        ids=[
            "autopurge_and_autosave",
            "no_autopurge_but_autosave",
            "autopurge_and_no_autosave",
            "no_autopurge_and_no_autosave",
        ],
    )
    def test_init_all_removes_stale_hosts(
        self,
        mock_config,
        mock_diskcache,
        cache_autopurge,
        cache_autosave,
        expected_purge,
    ):
        """
        Test that init_all removes hosts in cache that are no longer in
        the configuration file, while honoring cache_autopurge and
        cache_autosave settings.
        """
        mock_config["options"]["cache_autopurge"] = cache_autopurge
        mock_config["options"]["cache_autosave"] = cache_autosave
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.keys.return_value = ["host1", "host2", "stalehost"]

        _ = Inventory(mock_config)

        if expected_purge:
            cache_mock.__delitem__.assert_any_call("stalehost")
        else:
            cache_mock.__delitem__.assert_not_called()

    def test_save_state(self, mocker, mock_config, mock_diskcache):
        """
        Test that save_state saves all hosts to the cache using to_state().
        """

        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        for host in inventory.hosts:
            host.to_state = mocker.Mock(
                return_value=HostState(
                    os=None,
                    version=None,
                    flavor=None,
                    package_manager=None,
                    supported=True,
                    online=False,
                    updates=(),
                    last_refresh=None,
                )
            )

        inventory.save_state()

        for host in inventory.hosts:
            to_state_mock = host.to_state  # type: ignore[method-assign]
            to_state_mock.assert_called_once()  # type: ignore[attr-defined]
            cache_mock.__setitem__.assert_any_call(
                host.name,
                to_state_mock.return_value,  # type: ignore[attr-defined]
            )

    def test_clear_state(self, mocker, mock_config, mock_diskcache):
        """
        Test that clear_state clears the cache and re-initializes the inventory.
        """
        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        inventory.clear_state()

        cache_mock.clear.assert_called_once()
        assert len(inventory.hosts) == 5

    def test_clear_state_handles_file_not_found(
        self, mocker, mock_config, mock_diskcache
    ):
        """
        Test that clear_state handles FileNotFoundError gracefully.
        """
        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.clear.side_effect = FileNotFoundError

        try:
            inventory.clear_state()
        except Exception as e:
            pytest.fail(f"Unexpected exception raised: {e}")

    def test_clear_state_raises_on_other_exception(
        self, mocker, mock_config, mock_diskcache
    ):
        """
        Test that clear_state raises RuntimeError on other exceptions.
        """
        inventory = Inventory(mock_config)

        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.clear.side_effect = Exception("fail")

        with pytest.raises(RuntimeError):
            inventory.clear_state()

    def test_load_or_create_host_on_cache_miss(self, mocker, mock_diskcache):
        """
        Test that load_or_create_host creates a new Host on cache miss.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = False

        host_cfg = {"name": "testhost", "ip": "192.168.1.100", "port": 2222}
        result = inventory.load_or_create_host("testhost", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.name == "testhost"
        assert result.ip == "192.168.1.100"
        assert result.port == 2222
        # Ensure some defaults are defaulting
        assert result.os is None
        assert result.online is False

    def test_load_or_create_host_on_cache_error(self, mocker, mock_diskcache, caplog):
        """
        Test that load_or_create_host creates a new Host when cache read fails.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = True
        cache_mock.__getitem__.side_effect = Exception("corrupt cache")

        host_cfg = {"name": "testhost", "ip": "192.168.1.100", "port": 2222}

        with caplog.at_level("WARNING"):
            result = inventory.load_or_create_host("testhost", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.name == "testhost"

        # Assert some defaults are defaulting
        assert result.os is None
        assert result.online is False

        assert any(
            "Failed to load host state for testhost from cache" in m
            for m in caplog.messages
        )

    def test_load_or_create_host_with_hoststate_in_cache(self, mocker, mock_diskcache):
        """
        Test that load_or_create_host loads HostState from cache correctly.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        cached_state = HostState(
            os="linux",
            version="12",
            flavor="debian",
            package_manager="apt",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        cache_mock.__contains__.return_value = True
        cache_mock.__getitem__.return_value = cached_state

        host_cfg = {"name": "testhost", "ip": "192.168.1.100"}
        result = inventory.load_or_create_host("testhost", host_cfg, cache_mock)

        # Verify Host was constructed with config params
        assert isinstance(result, Host)
        assert result.name == "testhost"
        assert result.ip == "192.168.1.100"

        # Verify cached state was applied
        assert result.os == "linux"
        assert result.version == "12"
        assert result.flavor == "debian"
        assert result.package_manager == "apt"
        assert result.supported is True
        assert result.online is True

    def test_load_or_create_host_with_legacy_host_in_cache(
        self, mocker, mock_diskcache
    ):
        """
        Test that load_or_create_host calls migration for legacy Host objects.
        This ensures the inventory layer properly invokes the migration system.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        # Simulate legacy Host object in cache (old format)
        legacy_host = Host(name="oldhost", ip="192.168.1.50")
        legacy_host.os = "freebsd"
        legacy_host.version = "14"
        legacy_host.online = True

        cache_mock.__contains__.return_value = True
        cache_mock.__getitem__.return_value = legacy_host

        # We actually mock the migration code. The actual tests for this
        # live in the test_migrations.py suite.
        mock_migrate = mocker.patch("exosphere.inventory.migrations.migrate_from_host")
        mock_migrate.return_value = HostState(
            os="freebsd",
            version="14",
            flavor=None,
            package_manager="pkg",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        host_cfg = {"name": "oldhost", "ip": "192.168.1.50"}
        result = inventory.load_or_create_host("oldhost", host_cfg, cache_mock)

        # Verify migration was called
        mock_migrate.assert_called_once_with(legacy_host)
        assert isinstance(result, Host)
        assert result.name == "oldhost"
        assert result.os == "freebsd"
        assert result.version == "14"
        assert result.package_manager == "pkg"
        assert result.supported is True
        assert result.online is True

    def test_load_or_create_host_with_unknown_option(
        self, mocker, mock_diskcache, caplog
    ):
        """
        Test that load_or_create_host ignores unknown options in host configuration.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = False

        host_cfg = {
            "name": "host5",
            "ip": "127.0.0.8",
            "port": 22,
            "unknown_option": "should_be_ignored",
        }
        with caplog.at_level("WARNING"):
            result = inventory.load_or_create_host("host5", host_cfg, cache_mock)

        # Ensure the host is created without the unknown option
        assert isinstance(result, Host)
        assert result.name == "host5"
        assert result.ip == "127.0.0.8"
        assert result.port == 22
        assert not hasattr(result, "unknown_option")

        # Ensure the warning is logged
        assert any(
            "Invalid host configuration option 'unknown_option' for host 'host5', ignoring."
            in message
            for message in caplog.messages
        )

    def test_load_or_create_host_with_minimal_state(self, mocker, mock_diskcache):
        """
        Test that a HostState with all None values can be loaded.
        This represents a host that was never discovered.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = True

        minimal_state = HostState(
            os=None,
            version=None,
            flavor=None,
            package_manager=None,
            supported=True,
            online=False,
            updates=(),
            last_refresh=None,
        )

        cache_mock.__getitem__.return_value = minimal_state
        host_cfg = {"name": "minimal", "ip": "192.168.1.1"}
        result = inventory.load_or_create_host("minimal", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.name == "minimal"
        assert result.os is None
        assert result.version is None
        assert result.package_manager is None
        assert result._pkginst is None

    def test_load_or_create_host_with_unsupported_host(self, mocker, mock_diskcache):
        """
        Test that an unsupported host with package_manager doesn't crash.
        The from_state logic should not instantiate pkginst when supported=False.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = True

        state = HostState(
            os="unknown",
            version="0",
            flavor=None,
            package_manager="unknown_pm",
            supported=False,
            online=False,
            updates=(),
            last_refresh=None,
        )

        cache_mock.__getitem__.return_value = state
        host_cfg = {"name": "unsupported", "ip": "192.168.1.2"}
        result = inventory.load_or_create_host("unsupported", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.supported is False
        assert result._pkginst is None

    def test_load_or_create_host_with_contradictory_state(self, mocker, mock_diskcache):
        """
        Test contradictory state: package_manager set but os is None.
        This should not crash even though it's logically inconsistent,
        and a new Discover call will clean it right up anyways.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = True

        state = HostState(
            os=None,
            version=None,
            flavor=None,
            package_manager="apt",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        cache_mock.__getitem__.return_value = state
        host_cfg = {"name": "contradictory", "ip": "192.168.1.3"}
        result = inventory.load_or_create_host("contradictory", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.os is None
        assert result.package_manager == "apt"
        assert result._pkginst is not None

    def test_load_or_create_host_with_invalid_package_manager(
        self, mocker, mock_diskcache, caplog
    ):
        """
        Test that an invalid package manager name is handled gracefully.
        When PkgManagerFactory.create raises an error during from_state,
        load_or_create_host should catch it and create a fresh host.
        """
        from exosphere.objects import Host

        inventory = Inventory(Configuration())
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.__contains__.return_value = True

        state = HostState(
            os="linux",
            version="12",
            flavor="unknown",
            package_manager="invalid_pm_12345",
            supported=True,
            online=True,
            updates=(),
            last_refresh=None,
        )

        cache_mock.__getitem__.return_value = state

        mock_factory = mocker.patch("exosphere.objects.PkgManagerFactory.create")
        mock_factory.side_effect = ValueError("Unknown package manager")

        host_cfg = {"name": "invalidpm", "ip": "192.168.1.7"}

        with caplog.at_level("WARNING"):
            result = inventory.load_or_create_host("invalidpm", host_cfg, cache_mock)

        assert isinstance(result, Host)
        assert result.name == "invalidpm"
        assert result.os is None
        assert any("Failed to load host state" in m for m in caplog.messages)

    def test_get_host(self, mock_config):
        """
        Test that get_host retrieves a host by name from the inventory.
        """
        inventory = Inventory(mock_config)

        host = inventory.get_host("host2")

        assert host is not None
        assert host.name == "host2"
        assert host.ip == "127.0.0.2"
        assert host.port == 22

    def test_get_host_returns_none_if_not_found(self, mocker, mock_config, caplog):
        """
        Test that get_host returns None if the host is not found and logs an error.
        """
        inventory = Inventory(mock_config)

        with caplog.at_level("ERROR"):
            host = inventory.get_host("nonexistent")

        assert host is None
        assert any(
            "Host 'nonexistent' not found in inventory" in m for m in caplog.messages
        )

    @pytest.mark.parametrize(
        "mode, expected",
        [
            (FilterMode.NONE, {"alpha", "bravo", "charlie", "delta"}),
            (FilterMode.UPDATES_ONLY, {"alpha", "charlie"}),
            (FilterMode.SECURITY_ONLY, {"alpha", "charlie"}),
        ],
        ids=["none", "updates_only", "security_only"],
    )
    def test_filter_hosts(self, view_inventory, mode, expected):
        """
        Test that filter_hosts filters correctly based on mode.
        """
        result = view_inventory.filter_hosts(mode)
        assert {h.name for h in result} == expected

    def test_filter_hosts_returns_new_list(self, view_inventory):
        """
        Test that filter_hosts does not return the original list
        """
        result = view_inventory.filter_hosts(FilterMode.NONE)
        assert result is not view_inventory.hosts

    def test_filter_hosts_explicit_list(self, view_inventory):
        """
        Test that filter_hosts can filter a subset of hosts
        """
        subset = view_inventory.hosts[:2]
        result = view_inventory.filter_hosts(FilterMode.UPDATES_ONLY, hosts=subset)
        assert {h.name for h in result} == {"alpha"}

    @pytest.mark.parametrize(
        "field, reverse, expected",
        [
            (SortField.HOST, False, ["alpha", "bravo", "charlie", "delta"]),
            (SortField.HOST, True, ["delta", "charlie", "bravo", "alpha"]),
            # Supported counts: bravo 0, alpha 3, charlie 5; unsupported delta last
            (SortField.UPDATES, False, ["bravo", "alpha", "charlie", "delta"]),
            (SortField.UPDATES, True, ["charlie", "alpha", "bravo", "delta"]),
        ],
        ids=["host_asc", "host_desc", "updates_asc", "updates_desc"],
    )
    def test_sort_hosts_ordering(self, view_inventory, field, reverse, expected):
        """
        Test that hosts are sorted correctly (field, order)
        """
        result = view_inventory.sort_hosts(field, reverse=reverse)
        assert [h.name for h in result] == expected

    @pytest.mark.parametrize(
        "field",
        [
            SortField.FLAVOR,
            SortField.VERSION,
            SortField.UPDATES,
            SortField.SECURITY,
        ],
        ids=["flavor", "version", "updates", "security"],
    )
    def test_sort_hosts_unsupported_pinned_last(self, view_inventory, field):
        """
        Test that unsupported hosts are always sorted last on columns they lack
        """
        # Delta is unsupported, but reports an OS.
        # For any field other than host name, status and OS,
        # unsupported hosts must always land last, never interleaved
        # with real, meaningful data.
        result = view_inventory.sort_hosts(field)
        assert result[-1].name == "delta"

    def test_sort_hosts_os_includes_unsupported(self, mock_config, mocker):
        """
        Test that sorting by OS includes unsupported hosts.

        Unsupported hosts report an OS, so they sort by it alongside
        discovered hosts. Only undiscovered hosts (no OS at all) are pinned
        to the bottom for the OS column.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "z-discovered", os="ubuntu"),
            self._mkhost(mocker, "unsupported", os="arch", supported=False),
            self._mkhost(mocker, "a-discovered", os="debian"),
            self._mkhost(mocker, "undiscovered", os=None),
        ]

        result = inventory.sort_hosts(SortField.OS)

        # arch < debian < ubuntu by OS (unsupported interleaved), then the
        # undiscovered host (no OS) pinned last.
        assert [h.name for h in result] == [
            "unsupported",
            "a-discovered",
            "z-discovered",
            "undiscovered",
        ]

    def test_sort_hosts_pins_undiscovered_above_unsupported(self, mock_config, mocker):
        """
        Test the no-data hosts ordering on data columns.

        Discovered hosts sort on top, then undiscovered (no platform info),
        then unsupported, regardless of sort direction.
        """
        inventory = Inventory(mock_config)
        # Update counts for undiscovered and unsupported here are
        # intentionally high, something that would never happen in a
        # real inventory, to ensure they are properly ignored.
        inventory.hosts = [
            self._mkhost(mocker, "unsupported", os="plan9", supported=False, updates=9),
            self._mkhost(mocker, "undiscovered", os=None, updates=9),
            self._mkhost(mocker, "alpha", updates=5),
            self._mkhost(mocker, "bravo", updates=1),
        ]

        result = inventory.sort_hosts(SortField.UPDATES)
        assert [h.name for h in result] == [
            "bravo",
            "alpha",
            "undiscovered",
            "unsupported",
        ]

        # Reversed: only the discovered group flips; pinned hosts stay last.
        result = inventory.sort_hosts(SortField.UPDATES, reverse=True)
        assert [h.name for h in result] == [
            "alpha",
            "bravo",
            "undiscovered",
            "unsupported",
        ]

    def test_sort_hosts_by_status_online_first(self, view_inventory):
        """
        Test that hosts are sorted by status with online hosts first.
        """
        result = view_inventory.sort_hosts(SortField.STATUS)
        # Online (alpha, bravo) sort before offline (charlie, delta)
        assert [h.online for h in result] == [True, True, False, False]

    def test_sort_hosts_status_orders_all_hosts(self, mock_config, mocker):
        """
        Test that STATUS sorting never pins hosts.

        Online state is meaningful for every host, so undiscovered and
        unsupported hosts sort by their online state like any other.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "offline", os=None, online=False),
            self._mkhost(mocker, "alpha", os="plan9", supported=False, online=True),
            self._mkhost(mocker, "bravo", online=True),
        ]

        result = inventory.sort_hosts(SortField.STATUS)
        # Online hosts first (unsupported included), offline (undiscovered) last
        assert [h.online for h in result] == [True, True, False]
        assert result[-1].name == "offline"

    def test_sort_hosts_stable_preserves_config_order(self, mock_config, mocker):
        """
        Test that sorts hosts preserves config order when values compare equal

        Sort is stable, so this is an expected feature.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "first", updates=2),
            self._mkhost(mocker, "second", updates=2),
            self._mkhost(mocker, "third", updates=2),
        ]

        result = inventory.sort_hosts(SortField.UPDATES)
        assert [h.name for h in result] == ["first", "second", "third"]

    def test_sort_hosts_by_version_compound(self, mock_config, mocker):
        """
        Test that sorting by version compounds with flavor

        Versions are only meaningful within a flavor, so the sort
        should group by flavor first, and then natural sort the version
        within each flavor.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "deb-9", flavor="debian", version="9"),
            self._mkhost(mocker, "deb-12", flavor="debian", version="12"),
            self._mkhost(mocker, "ubu-22", flavor="ubuntu", version="22.04"),
            self._mkhost(mocker, "ubu-8", flavor="ubuntu", version="8"),
        ]

        result = inventory.sort_hosts(SortField.VERSION)

        # debian group first (deb-9 < deb-12 naturally), then ubuntu group
        assert [h.name for h in result] == ["deb-9", "deb-12", "ubu-8", "ubu-22"]

    def test_sort_hosts_by_flavor_groups_by_os(self, mock_config, mocker):
        """
        Test that sorting by flavor groups by OS first.

        Flavor is a refinement of OS, so OS families stay grouped (freebsd
        before linux) rather than interleaving alphabetically by flavor
        (which would wedge freebsd between debian and ubuntu).
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "ubuntu-host", os="linux", flavor="ubuntu"),
            self._mkhost(mocker, "freebsd-host", os="freebsd", flavor="freebsd"),
            self._mkhost(mocker, "debian-host", os="linux", flavor="debian"),
        ]

        result = inventory.sort_hosts(SortField.FLAVOR)

        # freebsd (OS) first, then the linux group sorted by flavor
        assert [h.name for h in result] == [
            "freebsd-host",
            "debian-host",
            "ubuntu-host",
        ]

    @pytest.mark.parametrize(
        "earlier, later",
        [
            ("9", "12"),  # numeric, not lexical (9 < 12)
            ("9.5", "9.10"),  # second segment compared as a number (5 < 10)
            ("14.0", "14.1"),
            ("14.3-RELEASE-p2", "14.3-RELEASE-p10"),  # FreeBSD style
            ("14.3-RELEASE-p12", "15.0-RELEASE-p9"),
            ("1", None),  # a known version sorts before an unknown one
            ("99.99", None),
        ],
        ids=[
            "numeric",
            "subsegment",
            "minor",
            "patch",
            "patch_major",
            "known<unknown",
            "any<unknown",
        ],
    )
    def test_sort_hosts_version_natural_order(
        self, mock_config, mocker, earlier, later
    ):
        """
        Test that version sorting compares in natural order, not lexical.
        """
        # Setup inventory with same flavor, both supported.
        # Sorting by version should reduce to pure natural sort on
        # version strings. Input order is reversed, so a no-op would
        # absolutely fail here.
        inventory = Inventory(mock_config)
        inventory.hosts = [
            self._mkhost(mocker, "beta", flavor="generic", version=later),
            self._mkhost(mocker, "alpha", flavor="generic", version=earlier),
        ]

        result = inventory.sort_hosts(SortField.VERSION)
        assert [h.name for h in result] == ["alpha", "beta"]

    def test_discover_all_calls_run_task(self, mocker, mock_config):
        """
        Test that discover_all calls run_task with 'discover'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory, "run_task", return_value=[(mock.Mock(name="host1"), None, None)]
        )

        inventory.discover_all()

        mock_run.assert_called_once_with(HostOperation.DISCOVER)

    def test_sync_repos_all_calls_run_task(self, mocker, mock_config):
        """
        Test that sync_repos_all calls run_task with 'sync_repos'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory,
            "run_task",
            return_value=[(mocker.Mock(name="host1"), None, None)],
        )

        inventory.sync_repos_all()

        mock_run.assert_called_once_with(HostOperation.SYNC)

    def test_refresh_updates_all_calls_run_task(self, mocker, mock_config):
        """
        Test that refresh_updates_all calls run_task with 'refresh_updates'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory,
            "run_task",
            return_value=[(mocker.Mock(name="host1"), None, None)],
        )

        inventory.refresh_updates_all()

        mock_run.assert_called_once_with(HostOperation.REFRESH)

    def test_ping_all_calls_run_task(self, mocker, mock_config):
        """
        Test that ping_all calls run_task with 'ping'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory,
            "run_task",
            return_value=[(mocker.Mock(name="host1"), None, None)],
        )

        inventory.ping_all()

        mock_run.assert_called_once_with(HostOperation.PING)

    def test_run_task_with_custom_host_list(self, mocker, mock_config):
        """
        Test that run_task works with a custom list of hosts.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)

        # Create hosts but only run task on subset
        mock_host1 = mocker.create_autospec(Host, instance=True)
        mock_host1.name = "host1"
        mock_host2 = mocker.create_autospec(Host, instance=True)
        mock_host2.name = "host2"
        mock_host3 = mocker.create_autospec(Host, instance=True)
        mock_host3.name = "host3"

        inventory.hosts = [mock_host1, mock_host2, mock_host3]

        # Setup return values
        mocker.patch.object(mock_host1, "ping", return_value=True)
        mocker.patch.object(mock_host2, "ping", return_value=True)

        # Run task only on subset of hosts
        results = list(
            inventory.run_task(HostOperation.PING, hosts=[mock_host1, mock_host2])
        )

        assert len(results) == 2
        assert all(result[2] is None for result in results)  # No exceptions
        assert {result[0].name for result in results} == {"host1", "host2"}

        # Verify host3.ping was never called
        assert not hasattr(mock_host3, "ping") or mock_host3.ping.call_count == 0

    @pytest.mark.parametrize("hosts_arg", [None, [], [{}]])
    def test_run_task_no_hosts(self, mocker, mock_config, hosts_arg, caplog):
        """
        Test run_task yields nothing and logs a warning if there are no hosts.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [] if hosts_arg is None else hosts_arg

        with caplog.at_level("WARNING"):
            task_generator = inventory.run_task(
                HostOperation.DISCOVER, hosts=None if hosts_arg is None else []
            )
            assert list(task_generator) == []
            assert any(
                "No hosts in inventory. Nothing to run." in message
                for message in caplog.messages
            )

    @pytest.mark.parametrize(
        "method_name",
        ["discover", "sync_repos", "refresh_updates", "ping"],
    )
    def test_run_task(self, mocker, mock_config, caplog, method_name):
        """
        Test run_task behavior with success and failure cases.
        """
        from exosphere.objects import Host

        operation = HostOperation(method_name)

        inventory = Inventory(mock_config)

        # Create two mock hosts
        mock_host1 = mocker.create_autospec(Host, instance=True)
        mock_host1.name = "host1"
        mock_host2 = mocker.create_autospec(Host, instance=True)
        mock_host2.name = "host2"

        # host1: method succeeds, host2: method raises exception
        mocker.patch.object(mock_host1, method_name, return_value="ok")
        mocker.patch.object(mock_host2, method_name, side_effect=RuntimeError("fail"))

        inventory.hosts = [mock_host1, mock_host2]

        results = list(inventory.run_task(operation))

        with caplog.at_level("DEBUG"):
            results = list(inventory.run_task(operation))

        assert len(results) == 2

        for host, result, exc in results:
            if host.name == "host1":
                assert result == "ok"
                assert exc is None
            elif host.name == "host2":
                assert result is None
                assert isinstance(exc, RuntimeError)
                assert str(exc) == "fail"

        assert any(
            f"Successfully executed {method_name} on host1" in m
            for m in caplog.messages
        )
        assert any(
            f"Failed to run {method_name} on host2: fail" in m for m in caplog.messages
        )

    @pytest.mark.parametrize(
        "method_name,should_raise,success_log,failure_log,completion_log",
        [
            (
                "discover",
                True,
                "Host host1 discovered successfully",
                "Failed to discover host host2: fail",
                "All hosts discovered",
            ),
            (
                "sync_repos",
                True,
                "Package repositories synced for host host1",
                "Failed to sync repositories for host host2: fail",
                "Package repositories synced for all hosts",
            ),
            (
                "refresh_updates",
                True,
                "Updates refreshed for host host1",
                "Failed to refresh updates for host host2: fail",
                "Updates refreshed for all hosts",
            ),
            (
                "ping",
                False,
                "Host host1 is online",
                "Host host2 is offline",
                "Pinged all hosts",
            ),
        ],
        ids=[
            "discover",
            "sync_repos",
            "refresh_updates",
            "ping",
        ],
    )
    def test_all_methods_log_individual_results(
        self,
        mocker,
        mock_config,
        caplog,
        method_name,
        should_raise,
        success_log,
        failure_log,
        completion_log,
    ):
        """
        Test that *_all methods log individual host results appropriately.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)

        # Create mock hosts with different outcomes
        mock_host1 = mocker.create_autospec(Host, instance=True)
        mock_host1.name = "host1"
        mock_host2 = mocker.create_autospec(Host, instance=True)
        mock_host2.name = "host2"

        # host1 succeeds, host2 fails
        if not should_raise:
            # Methods that don't raise exceptions return True/False
            mocker.patch.object(mock_host1, method_name, return_value=True)
            mocker.patch.object(mock_host2, method_name, return_value=False)
        else:
            mocker.patch.object(mock_host1, method_name, return_value=None)
            mocker.patch.object(
                mock_host2, method_name, side_effect=RuntimeError("fail")
            )

        inventory.hosts = [mock_host1, mock_host2]

        # Get corresponding method to call on Inventory
        target_method = getattr(inventory, f"{method_name}_all")

        with caplog.at_level("DEBUG"):
            target_method()

        assert any(success_log in m for m in caplog.messages)
        assert any(failure_log in m for m in caplog.messages)
        assert any(completion_log in m for m in caplog.messages)

    def test_ping_all_handles_unexpected_exceptions(self, mocker, mock_config, caplog):
        """
        Test that ping_all handles unexpected exceptions gracefully.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)

        mock_host = mocker.create_autospec(Host, instance=True)
        mock_host.name = "host1"
        # Force an exception that shouldn't normally happen
        mocker.patch.object(
            mock_host, "ping", side_effect=RuntimeError("unexpected error")
        )

        inventory.hosts = [mock_host]

        with caplog.at_level("INFO"):
            inventory.ping_all()

        assert any(
            "Failed to ping host host1: unexpected error" in m for m in caplog.messages
        )
        assert any("Pinged all hosts" in m for m in caplog.messages)

    def test_run_task_uses_max_threads_configuration(self, mocker, mock_config):
        """
        Test that run_task uses max_threads from configuration.
        """
        # Set specific max_threads value
        mock_config["options"]["max_threads"] = 5

        from exosphere.objects import Host

        inventory = Inventory(mock_config)
        mock_host = mocker.create_autospec(Host, instance=True)
        mock_host.name = "host1"
        inventory.hosts = [mock_host]

        # Mock ThreadPoolExecutor to verify max_workers
        mock_executor = mocker.patch("exosphere.inventory.ThreadPoolExecutor")
        mock_context = mocker.Mock()
        mock_executor.return_value.__enter__.return_value = mock_context

        # Mock the submit and as_completed behavior
        mock_future = mocker.Mock()
        mock_future.result.return_value = "success"
        mock_context.submit.return_value = mock_future
        mocker.patch("exosphere.inventory.as_completed", return_value=[mock_future])

        mocker.patch.object(mock_host, "ping", return_value=True)

        # Run the task
        list(inventory.run_task(HostOperation.PING))

        # Verify ThreadPoolExecutor was called with correct max_workers
        mock_executor.assert_called_once_with(max_workers=5)

    def test_close_all_closes_all_hosts(self, mocker, mock_config):
        """
        Test that close_all() calls close() on all hosts.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)
        mock_host = mocker.create_autospec(Host, instance=True)
        mock_host.name = "host1"
        mock_host2 = mocker.create_autospec(Host, instance=True)
        mock_host2.name = "host2"
        mock_host3 = mocker.create_autospec(Host, instance=True)
        mock_host3.name = "host3"
        inventory.hosts = [mock_host, mock_host2, mock_host3]

        mocker.patch.object(mock_host, "close")
        mocker.patch.object(mock_host2, "close")
        mocker.patch.object(mock_host3, "close")

        inventory.close_all()

        mock_host.close.assert_called_once_with(clear=False)
        mock_host2.close.assert_called_once_with(clear=False)
        mock_host3.close.assert_called_once_with(clear=False)

    def test_close_all_with_clear(self, mocker, mock_config):
        """
        Test that close_all(clear=True) passes clear flag to hosts.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)
        mock_host = mocker.create_autospec(Host, instance=True)
        mock_host.name = "host1"
        mock_host2 = mocker.create_autospec(Host, instance=True)
        mock_host2.name = "host2"
        inventory.hosts = [mock_host, mock_host2]

        mocker.patch.object(mock_host, "close")
        mocker.patch.object(mock_host2, "close")

        inventory.close_all(clear=True)

        mock_host.close.assert_called_once_with(clear=True)
        mock_host2.close.assert_called_once_with(clear=True)

    def test_close_all_with_empty_inventory(self):
        """
        Test that close_all() handles empty inventory gracefully.
        """
        config = Configuration()
        config.update_from_mapping({"hosts": []})
        inventory = Inventory(config)

        # Should not raise
        inventory.close_all()
        inventory.close_all(clear=True)
