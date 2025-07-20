import pytest
from typer.testing import CliRunner

from exosphere.commands import inventory as inventory_module
from exosphere.objects import Host

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_inventory(mocker):
    """
    Patch context inventory for all tests
    """
    fake_inventory = mocker.create_autospec(inventory_module.Inventory, instance=True)
    fake_inventory.hosts = []
    mocker.patch.object(inventory_module.context, "inventory", fake_inventory)
    return fake_inventory


def test_status_command_shows_table(mocker, mock_inventory):
    """
    Basic test for the status command to ensure it shows a table with host information.
    """

    host = mocker.create_autospec(Host, instance=True)
    host.name = "host1"
    host.os = "linux"
    host.flavor = "debian"
    host.version = "12"
    host.updates = [1, 2, 3, 4]
    host.security_updates = [1]
    host.online = True
    host.is_stale = False

    mock_inventory.hosts = [host]

    result = runner.invoke(inventory_module.app, ["status"])

    assert result.exit_code == 0
    assert "Host Status Overview" in result.output
    assert "host1" in result.output
    assert "linux" in result.output
    assert "debian" in result.output
    assert "12" in result.output
    assert "4" in result.output
    assert "1" in result.output
    assert "4 *" not in result.output  # No stale hosts
    assert "1 *" not in result.output  # No stale hosts
    assert "Online" in result.output


def test_status_command_with_stale_hosts(mocker, mock_inventory):
    """
    Test the status command to ensure it correctly identifies stale hosts.
    """
    host = mocker.create_autospec(Host, instance=True)
    host.name = "host1"
    host.os = "linux"
    host.flavor = "debian"
    host.version = "12"
    host.updates = [1, 2, 3, 4]
    host.security_updates = [1]
    host.online = True
    host.is_stale = True

    mock_inventory.hosts = [host]

    result = runner.invoke(inventory_module.app, ["status"])

    assert result.exit_code == 0
    assert "4 *" in result.output  # Stale hosts marked with *
    assert "1 *" in result.output  # Stale hosts marked with *


def test_status_command_no_hosts(mocker, mock_inventory):
    """
    Test the status command to ensure it handles the case with no hosts gracefully.
    """
    mock_inventory.hosts = []

    result = runner.invoke(inventory_module.app, ["status"])

    assert "No hosts found in inventory." in result.output
    assert result.exit_code == 0


def test_save_command_success(mocker, mock_inventory):
    """
    Test the save command to ensure it calls the save_state method on the inventory.
    """
    mock_inventory.save_state = mocker.Mock()

    result = runner.invoke(inventory_module.app, ["save"])

    assert result.exit_code == 0
    mock_inventory.save_state.assert_called_once()


def test_save_command_failure(mocker, mock_inventory):
    """
    Test the save command to ensure it handles exceptions raised by save_state.
    """
    mock_inventory.save_state = mocker.Mock(side_effect=Exception("fail"))

    result = runner.invoke(inventory_module.app, ["save"])

    assert result.exit_code != 0
    assert "Error saving inventory state" in result.output


def test_clear_command_success(mocker, mock_inventory):
    """
    Test the clear command to ensure it clears the inventory.
    """
    mock_clear = mock_inventory.clear_state = mocker.Mock()

    result = runner.invoke(inventory_module.app, ["clear", "--force"])

    assert result.exit_code == 0
    mock_clear.assert_called_once()
    assert "Inventory state has been cleared" in result.output


def test_clear_command_no_force(mocker, mock_inventory):
    """
    Test the clear command to ensure it prompts for confirmation when --force is not used.
    """
    result = runner.invoke(inventory_module.app, ["clear"])

    assert result.exit_code != 0
    assert "Confirm [y/n]" in result.output


def test_clear_command_confirmation(mocker, mock_inventory):
    """
    Test the clear command to ensure it clears the inventory when confirmed.
    """
    mock_inventory.clear_state = mocker.Mock()

    result = runner.invoke(inventory_module.app, ["clear"], input="y\n")

    assert result.exit_code == 0
    mock_inventory.clear_state.assert_called_once()
    assert "Inventory state has been cleared" in result.output


def test_clear_command_cancelled(mocker, mock_inventory):
    """
    Test the clear command to ensure it does not clear the inventory when cancelled.
    """
    mock_inventory.clear_state = mocker.Mock()

    result = runner.invoke(inventory_module.app, ["clear"], input="n\n")

    assert result.exit_code != 0
    mock_inventory.clear_state.assert_not_called()
    assert "Inventory state has not been cleared" in result.output


def test_clear_command_failure(mocker, mock_inventory):
    """
    Test the clear command to ensure it handles exceptions raised by clear_state.
    """
    mock_inventory.clear_state = mocker.Mock(side_effect=Exception("beefed it"))

    result = runner.invoke(inventory_module.app, ["clear", "--force"])

    assert result.exit_code != 0
    assert "Error clearing inventory state" in result.output
