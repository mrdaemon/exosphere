import pytest

from exosphere.ui.messages import HostStatusChanged, ScreenFlagsRegistry


@pytest.fixture
def registry():
    return ScreenFlagsRegistry()


def test_host_status_changed_initialization():
    """
    Test that HostStatusChanged message initializes with the correct screen name.
    """
    msg = HostStatusChanged("main_screen")
    assert msg.current_screen == "main_screen"


def test_register_screens_adds_new_screens(registry, caplog):
    """
    Test that the register_screens method adds new screens to the registry.
    """
    with caplog.at_level("DEBUG"):
        registry.register_screens("screen1", "screen2")

    assert "screen1" in registry.registered_screens
    assert "screen2" in registry.registered_screens
    assert "Registered screen: screen1" in caplog.text
    assert "Registered screen: screen2" in caplog.text


def test_register_screens_warns_on_duplicate(registry, caplog):
    """
    Test that the register_screens method warns on duplicate screen registration.
    """
    registry.registered_screens = ["screen1"]

    with caplog.at_level("WARNING"):
        registry.register_screens("screen1")

    assert "Screen 'screen1' is already registered." in caplog.text


def test_flag_screen_dirty_flags_only_registered(registry, caplog):
    """
    Test that the flag_screen_dirty method only flags registered screens as dirty.
    """
    registry.registered_screens = ["screen1", "screen2"]

    with caplog.at_level("DEBUG"):
        registry.flag_screen_dirty("screen1", "screen3")

    assert registry.dirty_screens["screen1"] is True
    assert "screen3" not in registry.dirty_screens
    assert "Attempted to flag unregistered screen as dirty: screen3" in caplog.text
    assert "Flagging screen 'screen1' as dirty." in caplog.text


def test_flag_screen_clean_removes_dirty_flag(registry, caplog):
    """
    Test that the flag_screen_clean method removes the dirty flag from a screen.
    """
    registry.dirty_screens = {"screen1": True, "screen2": True}

    with caplog.at_level("DEBUG"):
        registry.flag_screen_clean("screen1")

    assert "screen1" not in registry.dirty_screens
    assert "screen2" in registry.dirty_screens
    assert "Flagging screen 'screen1' as clean." in caplog.text


def test_flag_screen_dirty_except_flags_all_but_current(registry, caplog):
    """
    Test that the flag_screen_dirty_except method flags all registered
    screens as dirty except the current one.
    """
    registry.registered_screens = ["screen1", "screen2", "screen3"]

    with caplog.at_level("DEBUG"):
        registry.flag_screen_dirty_except("screen2")

    assert registry.dirty_screens["screen1"] is True
    assert registry.dirty_screens["screen3"] is True
    assert "screen2" not in registry.dirty_screens


def test_flag_screen_dirty_except_no_registered_screens(registry, caplog):
    """
    Test that the flag_screen_dirty_except method handles the case
    where there are no registered screens.
    """
    with caplog.at_level("WARNING"):
        registry.flag_screen_dirty_except("screen1")

    assert "No registered screens to flag as dirty." in caplog.text


def test_flag_screen_dirty_except_no_other_screens(registry, caplog):
    """
    Test that the flag_screen_dirty_except method handles the case
    where there are no other registered screens.
    """
    registry.registered_screens = ["screen1"]

    with caplog.at_level("DEBUG"):
        registry.flag_screen_dirty_except("screen1")

    assert "No screens to flag as dirty (excluding current)." in caplog.text


def test_is_screen_dirty_returns_true_and_false(registry):
    """
    Test that is_screen_dirty returns appropriate boolean values
    """

    registry.dirty_screens = {"screen1": True}

    assert registry.is_screen_dirty("screen1") is True
    assert registry.is_screen_dirty("screen2") is False


def test_clear_dirty_screens_clears_all(registry, caplog):
    """
    Test that clear_dirty_screens removes all dirty flags.
    """

    registry.dirty_screens = {"screen1": True, "screen2": True}

    with caplog.at_level("DEBUG"):
        registry.clear_dirty_screens()

    assert registry.dirty_screens == {}
    assert "Clearing all dirty screens." in caplog.text
