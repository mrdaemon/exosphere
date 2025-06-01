from unittest import mock

import pytest

from exosphere.config import Configuration
from exosphere.inventory import Inventory


class TestInventory:
    @pytest.fixture
    def mock_config(self):
        data = {
            "options": {"cache_file": "test_cache.db"},
            "hosts": [
                {"name": "host1", "ip": "127.0.0.1", "port": 22},
                {"name": "host2", "ip": "127.0.0.2", "port": 22},
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
        import exosphere.objects

        def make_mock_host(**kwargs):
            m = mocker.create_autospec(exosphere.objects.Host, instance=True, **kwargs)
            m.name = kwargs.get("name", "mock_host")
            m.ip = kwargs.get("ip", "127.0.0.1")
            m.port = kwargs.get("port", 22)
            return m

        patcher = mocker.patch("exosphere.inventory.Host", side_effect=make_mock_host)
        return patcher

    def test_init_all(self, mocker, mock_config, mock_diskcache, mock_host_class):
        """
        Test that init_all creates Host objects from the configuration.
        """
        inventory = Inventory(mock_config)
        assert len(inventory.hosts) == 2

    def test_init_all_removes_stale_hosts(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that init_all removes hosts that are not in the configuration from cache.
        """
        cache_mock = mock_diskcache.return_value.__enter__.return_value
        cache_mock.keys.return_value = ["host1", "host2", "stalehost"]

        _ = Inventory(mock_config)

        cache_mock.__delitem__.assert_any_call("stalehost")

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
        assert len(inventory.hosts) == 2

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

    def test_refresh_catalog_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that refresh_catalog_all calls run_task with 'refresh_catalog'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory, "run_task", return_value=[(mock.Mock(name="host1"), None, None)]
        )

        inventory.refresh_catalog_all()

        mock_run.assert_called_once_with("refresh_catalog")

    def test_refresh_updates_all_calls_run_task(
        self, mocker, mock_config, mock_diskcache, mock_host_class
    ):
        """
        Test that refresh_updates_all calls run_task with 'refresh_updates'.
        """
        inventory = Inventory(mock_config)
        mock_run = mocker.patch.object(
            inventory, "run_task", return_value=[(mock.Mock(name="host1"), None, None)]
        )

        inventory.refresh_updates_all()

        mock_run.assert_called_once_with("refresh_updates")

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
