from exosphere.ui.messages import ScreenFlagsRegistry


def test_screen_flags_registry_initialization():
    """
    Ensure ScreenFlagsRegistry automatically initializes when
    context is imported.
    """
    from exosphere.ui import context

    assert context.screenflags is not None
    assert isinstance(context.screenflags, ScreenFlagsRegistry)
