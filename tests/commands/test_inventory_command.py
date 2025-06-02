from unittest import mock

import pytest
from typer.testing import CliRunner

from exosphere.commands import inventory as inventory_module
from exosphere.objects import Host

runner = CliRunner()


@pytest.fixture(autouse=True)
def patch_context_inventory(monkeypatch):
    """
    Patch context inventory for all tests
    """
    fake_inventory = mock.Mock()
    fake_inventory.hosts = []
    monkeypatch.setattr(inventory_module.context, "inventory", fake_inventory)
    return fake_inventory


def test_status_command_shows_table(mocker, monkeypatch, patch_context_inventory):
    """
    Basic test for the status command to ensure it shows a table with host information.
    """

    host = mocker.create_autospec(Host, instance=True)
    host.name = "host1"
    host.os = "Linux"
    host.flavor = "Debian"
    host.version = "10"
    host.updates = [1, 2]
    host.security_updates = [1]
    host.online = True
    host.is_stale = False

    patch_context_inventory.hosts = [host]
    monkeypatch.setattr(
        inventory_module, "_get_inventory", lambda: patch_context_inventory
    )

    result = runner.invoke(inventory_module.app, ["status"])

    assert "Host Status Overview" in result.output
    assert "host1" in result.output


def test_save_command_success(mocker, monkeypatch, patch_context_inventory):
    """
    Test the save command to ensure it calls the save_state method on the inventory.
    """
    patch_context_inventory.save_state = mocker.Mock()
    monkeypatch.setattr(
        inventory_module, "_get_inventory", lambda: patch_context_inventory
    )

    result = runner.invoke(inventory_module.app, ["save"])

    assert result.exit_code == 0
    patch_context_inventory.save_state.assert_called_once()


def test_save_command_failure(mocker, monkeypatch, patch_context_inventory):
    """
    Test the save command to ensure it handles exceptions raised by save_state.
    """
    patch_context_inventory.save_state = mocker.Mock(side_effect=Exception("fail"))
    monkeypatch.setattr(
        inventory_module, "_get_inventory", lambda: patch_context_inventory
    )

    result = runner.invoke(inventory_module.app, ["save"])

    assert "Error saving inventory state" in result.output
