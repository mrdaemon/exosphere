from unittest import mock

import pytest

from exosphere.config import Configuration
from exosphere.inventory import Inventory
from exosphere.security import SudoPolicy


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

    @pytest.fixture
    def mock_diskcache(self, mocker):
        mock_dc = mocker.patch("exosphere.inventory.DiskCache")
        return mock_dc

    @pytest.fixture
    def mock_host_class(self, mocker):
        """
        Mock the Host class fairly in depth to ensure it behaves like the real one.
        This includes faking the signature of the __init__ method.
        """
        from inspect import Parameter, Signature

        import exosphere.objects

        original_optional_params = exosphere.objects.Host.OPTIONAL_PARAMS

        def make_mock_host(**kwargs):
            m = mocker.create_autospec(exosphere.objects.Host, instance=True, **kwargs)
            m.name = kwargs.get("name", "mock_host")
            m.ip = kwargs.get("ip", "127.0.0.1")
            m.port = kwargs.get("port", 22)
            m.description = kwargs.get("description", None)
            m.username = kwargs.get("username", None)
            m.sudo_policy = kwargs.get("sudo_policy", SudoPolicy.SKIP)
            m.close = mocker.Mock()
            return m

        patcher = mocker.patch("exosphere.inventory.Host", side_effect=make_mock_host)

        # Conserve the original OPTIONAL_PARAMS constant from the Host class
        # Those are serialization hints
        patcher.OPTIONAL_PARAMS = original_optional_params

        mock_signature = Signature(
            parameters=[
                Parameter("self", Parameter.POSITIONAL_OR_KEYWORD),
                Parameter("name", Parameter.POSITIONAL_OR_KEYWORD),
                Parameter("ip", Parameter.POSITIONAL_OR_KEYWORD),
                Parameter("port", Parameter.POSITIONAL_OR_KEYWORD, default=22),
                Parameter("username", Parameter.POSITIONAL_OR_KEYWORD, default=None),
                Parameter("description", Parameter.POSITIONAL_OR_KEYWORD, default=None),
                Parameter(
                    "connect_timeout", Parameter.POSITIONAL_OR_KEYWORD, default=30
                ),
                Parameter(
                    "sudo_policy",
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=SudoPolicy.SKIP,
                ),
            ]
        )

        mocker.patch(
            "exosphere.inventory.inspect.signature", return_value=mock_signature
        )

        return patcher

    def test_init_all(self, mocker, mock_config, mock_diskcache, mock_host_class):
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

    def test_init_all_with_empty_hosts(self, mocker, mock_diskcache, caplog):
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

    def test_init_all_removes_stale_hosts(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that init_all removes hosts that are not in the configuration from cache
        by default
        """
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.keys.return_value = ["host1", "host2", "stalehost"]

        _ = Inventory(mock_config)

        cache_mock.__delitem__.assert_any_call("stalehost")

    def test_init_all_does_not_remove_stale_hosts(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that init_all does not remove stale hosts from cache if configured to do so.
        """
        mock_config["options"]["cache_autopurge"] = False
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.keys.return_value = ["host1", "host2", "stalehost"]

        _ = Inventory(mock_config)

        cache_mock.__delitem__.assert_not_called()

    def test_save_state(self, mocker, mock_config, mock_diskcache, mock_host_class):
        """
        Test that save_state saves all hosts to the cache.
        """
        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        inventory.save_state()

        for host in inventory.hosts:
            cache_mock.__setitem__.assert_any_call(host.name, host)

    def test_clear_state(self, mocker, mock_config, mock_diskcache, mock_host_class):
        """
        Test that clear_state clears the cache and re-initializes the inventory.
        """
        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        inventory.clear_state()

        cache_mock.clear.assert_called_once()
        assert len(inventory.hosts) == 5

    def test_clear_state_handles_file_not_found(
        self, mocker, mock_config, mock_diskcache, mock_host_class
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
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that clear_state raises RuntimeError on other exceptions.
        """
        inventory = Inventory(mock_config)

        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.clear.side_effect = Exception("fail")

        with pytest.raises(RuntimeError):
            inventory.clear_state()

    @pytest.mark.parametrize(
        "host_name,host_cfg,cache_contains,cache_getitem_side_effect,expect_new,expect_warning",
        [
            (
                "host1",
                {"name": "host1", "ip": "127.0.0.1", "port": 2222},
                lambda k: k == "host1",
                lambda k: mock.Mock(name="host1_mock") if k == "host1" else KeyError,
                False,
                False,
            ),
            (
                "host2",
                {"name": "host2", "ip": "127.0.0.2", "port": 2222},
                lambda k: False,
                None,
                True,
                False,
            ),
            (
                "host3",
                {"name": "host3", "ip": "127.0.0.3", "port": 2222},
                lambda k: True,
                Exception("corrupt cache or whatever"),
                True,
                True,
            ),
        ],
        ids=[
            "load_on_cache_hit",
            "create_on_cache_miss",
            "create_on_cache_error",
        ],
    )
    def test_load_or_create_host(
        self,
        mocker,
        mock_config,
        mock_diskcache,
        mock_host_class,
        caplog,
        host_name,
        host_cfg,
        cache_contains,
        cache_getitem_side_effect,
        expect_new,
        expect_warning,
    ):
        """
        Test load_or_create_host behavior with various cache states.
        """
        inventory = Inventory(mock_config)
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        # Horrying kludge to mock cache behavior
        cache_mock.__contains__.side_effect = cache_contains

        if callable(cache_getitem_side_effect):

            def modified_getitem(k):
                if k == host_name:
                    return mock_host_class(**host_cfg)
                else:
                    raise KeyError(k)

            cache_mock.__getitem__.side_effect = modified_getitem

        if isinstance(cache_getitem_side_effect, Exception):
            cache_mock.__getitem__.side_effect = cache_getitem_side_effect

        if expect_warning:
            with caplog.at_level("WARNING"):
                result = inventory.load_or_create_host(host_name, host_cfg, cache_mock)
        else:
            result = inventory.load_or_create_host(host_name, host_cfg, cache_mock)

        if expect_new:
            mock_host_class.assert_any_call(**host_cfg)
            assert result.name == host_cfg["name"]
            assert result.ip == host_cfg["ip"]
            assert result.port == host_cfg["port"]
        else:
            assert result.name == host_cfg["name"]
            assert result.ip == host_cfg["ip"]
            assert result.port == host_cfg["port"]

        if expect_warning:
            assert any(
                f"Failed to load host state for {host_name} from cache" in m
                for m in caplog.messages
            )

    def test_load_or_create_host_with_unknown_option(
        self, mocker, mock_diskcache, mock_config, caplog
    ):
        """
        Test that load_or_create_host ignores unknown options in host configuration.
        """
        inventory = Inventory(mock_config)

        host_cfg = {
            "name": "host5",
            "ip": "127.0.0.8",
            "port": 22,
            "unknown_option": "should_be_ignored",
        }
        with caplog.at_level("WARNING"):
            result = inventory.load_or_create_host("host5", host_cfg, mock_diskcache)

        # Ensure the host is created without the unknown option
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

    def test_load_or_create_host_with_removed_option_in_cache(
        self,
        mocker,
        mock_diskcache,
        mock_host_class,
        caplog,
    ):
        """
        Test that load_or_create_host handles removed options from config
        that are present in the cache gracefully. They are expected to be
        reset to their default values.
        """

        # Configuration with a single host with no options
        config_data = {
            "options": {
                "cache_file": "test_cache.db",
            },
            "hosts": [
                {
                    "name": "host99",
                    "ip": "127.0.0.99",
                },
            ],
        }

        config = Configuration()
        config.update_from_mapping(config_data)

        inventory = Inventory(config)

        # Simulate a host in the cache with options that have been removed from config
        cache_mock = mock_diskcache.return_value.__enter__.return_value

        cached_host = mocker.create_autospec(
            spec="exosphere.objects.Host", instance=True
        )
        cached_host.name = "host99"
        cached_host.ip = "127.0.0.99"
        cached_host.port = 2222
        cached_host.username = "megaroot"
        cached_host.description = "test host"
        cached_host.connect_timeout = 999
        cached_host.sudo_policy = SudoPolicy.NOPASSWD

        # Cache returns cached host
        cache_mock.__contains__.side_effect = lambda k: k == "host99"
        cache_mock.__getitem__.side_effect = (
            lambda k: cached_host if k == "host99" else KeyError(k)
        )

        # Reset mock before actual test
        mock_host_class.reset_mock()

        result = inventory.load_or_create_host("host99", config["hosts"][0], cache_mock)

        # Ensure the host is loaded from cache and not actually created
        mock_host_class.assert_not_called()

        # Ensure the host is created with default values for removed options
        assert result.name == "host99"
        assert result.ip == "127.0.0.99"
        assert result.port == 22  # Default port
        assert result.username is None
        assert result.description is None
        assert result.connect_timeout == config["options"]["default_timeout"]
        assert result.sudo_policy == SudoPolicy(
            config["options"]["default_sudo_policy"]
        )

    def test_get_host(self, mocker, mock_config):
        """
        Test that get_host retrieves a host by name from the inventory.
        """
        inventory = Inventory(mock_config)

        host = inventory.get_host("host2")

        assert host is not None
        assert host.name == "host2"
        assert host.ip == "127.0.0.2"
        assert host.port == 22

    def test_get_host_returns_none_if_not_found(self, mocker, mock_config):
        """
        Test that get_host returns None if the host is not found.
        """
        inventory = Inventory(mock_config)

        host = inventory.get_host("nonexistent")

        assert host is None

    def test_discover_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that discover_all calls run_task with 'discover'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory, "run_task", return_value=[(mock.Mock(name="host1"), None, None)]
        )

        inventory.discover_all()

        mock_run.assert_called_once_with("discover")

    def test_sync_repos_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
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

        mock_run.assert_called_once_with("sync_repos")

    def test_refresh_updates_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
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

        mock_run.assert_called_once_with("refresh_updates")

    def test_ping_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
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

        mock_run.assert_called_once_with("ping")

    def test_run_task_with_custom_host_list(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that run_task works with a custom list of hosts.
        """
        inventory = Inventory(mock_config)

        # Create hosts but only run task on subset
        mock_host1 = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")
        mock_host3 = mock_host_class(name="host3", ip="127.0.0.3")

        inventory.hosts = [mock_host1, mock_host2, mock_host3]

        # Setup return values
        mocker.patch.object(mock_host1, "ping", return_value=True)
        mocker.patch.object(mock_host2, "ping", return_value=True)

        # Run task only on subset of hosts
        results = list(inventory.run_task("ping", hosts=[mock_host1, mock_host2]))

        assert len(results) == 2
        assert all(result[2] is None for result in results)  # No exceptions
        assert {result[0].name for result in results} == {"host1", "host2"}

        # Verify host3.ping was never called
        assert not hasattr(mock_host3, "ping") or mock_host3.ping.call_count == 0

    @pytest.mark.parametrize("hosts_arg", [None, [], [{}]])
    def test_run_task_no_hosts(
        self, mocker, mock_config, mock_diskcache, mock_host_class, hosts_arg, caplog
    ):
        """
        Test run_task yields nothing and logs a warning if there are no hosts.
        """
        inventory = Inventory(mock_config)
        inventory.hosts = [] if hosts_arg is None else hosts_arg

        with caplog.at_level("WARNING"):
            task_generator = inventory.run_task(
                "discover", hosts=None if hosts_arg is None else []
            )
            assert list(task_generator) == []
            assert any(
                "No hosts in inventory. Nothing to run." in message
                for message in caplog.messages
            )

    def test_run_task_method_not_exists(
        self, mocker, mock_config, mock_diskcache, caplog
    ):
        """
        Test run_task yields nothing and logs error if method does not exist on Host.
        """
        from exosphere.objects import Host

        inventory = Inventory(mock_config)
        mock_host = mocker.create_autospec(Host, instance=True)

        inventory.hosts = [mock_host]

        with caplog.at_level("ERROR"):
            task_generator = inventory.run_task("invalid_method")
            assert list(task_generator) == []
            assert any(
                "Host class does not have attribute 'invalid_method', refusing to execute!"
                in message
                for message in caplog.messages
            )

    def test_run_task_method_not_callable(
        self, mocker, mock_config, mock_diskcache, mock_host_class, caplog
    ):
        """
        Test run_task yields nothing and logs error if method is not callable.
        """
        import exosphere.inventory

        inventory = Inventory(mock_config)
        mock_host = mock_host_class.return_value

        # Set an attribute that is not callable
        mocker.patch.object(
            exosphere.inventory.Host, "not_callable", "Hi it's me, ur string"
        )

        inventory.hosts = [mock_host]

        with caplog.at_level("ERROR"):
            task_generator = inventory.run_task("not_callable")
            assert list(task_generator) == []
            assert any(
                "Host class attribute 'not_callable' is not callable, refusing to execute!"
                in message
                for message in caplog.messages
            )

    @pytest.mark.parametrize(
        "method_name",
        ["discover", "sync_repos", "refresh_updates", "ping"],
    )
    def test_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class, caplog, method_name
    ):
        """
        Test run_task behavior with success and failure cases.
        """
        inventory = Inventory(mock_config)

        # Create two mock hosts
        mock_host1 = mock_host_class(name="host1", ip="127.0.0.1", port=22)
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2", port=22)

        # host1: method succeeds, host2: method raises exception
        mocker.patch.object(mock_host1, method_name, return_value="ok")
        mocker.patch.object(mock_host2, method_name, side_effect=RuntimeError("fail"))

        inventory.hosts = [mock_host1, mock_host2]

        results = list(inventory.run_task(method_name))

        with caplog.at_level("DEBUG"):
            results = list(inventory.run_task(method_name))

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
        mock_diskcache,
        mock_host_class,
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
        inventory = Inventory(mock_config)

        # Create mock hosts with different outcomes
        mock_host1 = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")

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

        with caplog.at_level("INFO"):
            target_method()

        assert any(success_log in m for m in caplog.messages)
        assert any(failure_log in m for m in caplog.messages)
        assert any(completion_log in m for m in caplog.messages)

    def test_ping_all_handles_unexpected_exceptions(
        self, mocker, mock_config, mock_diskcache, mock_host_class, caplog
    ):
        """
        Test that ping_all handles unexpected exceptions gracefully.
        """
        inventory = Inventory(mock_config)

        mock_host = mock_host_class(name="host1", ip="127.0.0.1")
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

    def test_run_task_uses_max_threads_configuration(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that run_task uses max_threads from configuration.
        """
        # Set specific max_threads value
        mock_config["options"]["max_threads"] = 5

        inventory = Inventory(mock_config)
        mock_host = mock_host_class(name="host1", ip="127.0.0.1")
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
        list(inventory.run_task("ping"))

        # Verify ThreadPoolExecutor was called with correct max_workers
        mock_executor.assert_called_once_with(max_workers=5)

    def test_run_task_closes_connections_when_pipelining_disabled(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that connections are closed when ssh_pipelining is disabled.
        """
        # Ensure ssh_pipelining is disabled (default)
        mock_config["options"]["ssh_pipelining"] = False

        inventory = Inventory(mock_config)
        mock_host1 = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")
        inventory.hosts = [mock_host1, mock_host2]

        mocker.patch.object(mock_host1, "ping", return_value=True)
        mocker.patch.object(mock_host2, "ping", return_value=True)

        # Run the task
        list(inventory.run_task("ping"))

        # Verify that close was called on both hosts
        mock_host1.close.assert_called_once_with(clear=False)
        mock_host2.close.assert_called_once_with(clear=False)

    def test_run_task_keeps_connections_when_pipelining_enabled(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that connections are NOT closed when ssh_pipelining is enabled.
        """
        # Enable ssh_pipelining
        mock_config["options"]["ssh_pipelining"] = True

        inventory = Inventory(mock_config)
        mock_host1 = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")
        inventory.hosts = [mock_host1, mock_host2]

        mocker.patch.object(mock_host1, "ping", return_value=True)
        mocker.patch.object(mock_host2, "ping", return_value=True)

        # Run the task
        list(inventory.run_task("ping"))

        # Verify that close was NOT called on either host
        mock_host1.close.assert_not_called()
        mock_host2.close.assert_not_called()

    def test_run_task_closes_connections_even_on_exception(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that connections are closed even when a task raises an exception
        (when ssh_pipelining is disabled).
        """
        # Ensure ssh_pipelining is disabled
        mock_config["options"]["ssh_pipelining"] = False

        inventory = Inventory(mock_config)
        mock_host = mock_host_class(name="host1", ip="127.0.0.1")
        inventory.hosts = [mock_host]

        # Ensure task raises an exception
        mocker.patch.object(mock_host, "ping", side_effect=RuntimeError("Test error"))

        # Run the task, exception will be in tuple
        results = list(inventory.run_task("ping"))

        # Sanity check, we should have an exception
        assert len(results) == 1
        host, result, exc = results[0]
        assert host == mock_host
        assert result is None
        assert isinstance(exc, RuntimeError)

        # Ensure connection was closed explicitly
        mock_host.close.assert_called_once_with(clear=False)

    def test_close_all_closes_all_hosts(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that close_all() calls close() on all hosts.
        """
        inventory = Inventory(mock_config)
        mock_host = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")
        mock_host3 = mock_host_class(name="host3", ip="127.0.0.3")
        inventory.hosts = [mock_host, mock_host2, mock_host3]

        mocker.patch.object(mock_host, "close")
        mocker.patch.object(mock_host2, "close")
        mocker.patch.object(mock_host3, "close")

        inventory.close_all()

        mock_host.close.assert_called_once_with(clear=False)
        mock_host2.close.assert_called_once_with(clear=False)
        mock_host3.close.assert_called_once_with(clear=False)

    def test_close_all_with_clear(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that close_all(clear=True) passes clear flag to hosts.
        """
        inventory = Inventory(mock_config)
        mock_host = mock_host_class(name="host1", ip="127.0.0.1")
        mock_host2 = mock_host_class(name="host2", ip="127.0.0.2")
        inventory.hosts = [mock_host, mock_host2]

        mocker.patch.object(mock_host, "close")
        mocker.patch.object(mock_host2, "close")

        inventory.close_all(clear=True)

        mock_host.close.assert_called_once_with(clear=True)
        mock_host2.close.assert_called_once_with(clear=True)

    def test_close_all_with_empty_inventory(self, mocker, mock_diskcache):
        """
        Test that close_all() handles empty inventory gracefully.
        """
        config = Configuration()
        config.update_from_mapping({"hosts": []})
        inventory = Inventory(config)

        # Should not raise
        inventory.close_all()
        inventory.close_all(clear=True)
