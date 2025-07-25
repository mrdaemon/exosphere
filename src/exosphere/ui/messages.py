"""
UI Messages and Events Module

This defines custom messages and events used within the Exosphere TUI
application, as well as support classes such as the Screen Flags
registry.
"""

import logging

from textual.message import Message


class HostStatusChanged(Message):
    """Message to notify that a host's status has changed."""

    def __init__(self, current_screen: str) -> None:
        super().__init__()
        self.current_screen = current_screen


class ScreenFlagsRegistry:
    """
    Registry to track async flags for screens in the UI

    This registry allows (so far) to flag screens as dirty or clean,
    indicating whether they need to be refreshed or not.

    This allows a screen to mutate the data model in some meaningful
    way, and then flag other screens as dirty, so that the next time
    we switch to them in the modal application, they will know to
    refresh their views of the data.
    """

    def __init__(self) -> None:
        self.registered_screens: list[str] = []
        self.dirty_screens: dict[str, bool] = {}
        self.logger = logging.getLogger("exosphere.ui.messages")

    def register_screens(self, *screen_name: str) -> None:
        """
        Register Textual Screen names to the flags registry.

        It's intended to receive straight up SCREENS.keys() but
        you can also just pass in a list of screen names.
        """
        for screen in screen_name:
            if screen not in self.registered_screens:
                self.registered_screens.append(screen)
                self.logger.debug(f"Registered screen: {screen}")
            else:
                self.logger.warning(f"Screen '{screen}' is already registered.")

    def flag_screen_dirty(self, *screen_name: str) -> None:
        """
        Flag one or more screens as dirty so they can be refreshed
        """

        for screen in screen_name:
            if screen not in self.registered_screens:
                self.logger.warning(
                    f"Attempted to flag unregistered screen as dirty: {screen}"
                )
                continue

            self.logger.debug(f"Flagging screen '{screen}' as dirty.")
            self.dirty_screens[screen] = True

    def flag_screen_clean(self, *screen_name: str) -> None:
        """
        Flag a screen as clean
        """
        for screen in screen_name:
            if screen in self.dirty_screens:
                self.logger.debug(f"Flagging screen '{screen}' as clean.")
                del self.dirty_screens[screen]

    def flag_screen_dirty_except(self, current_screen: str) -> None:
        """
        Flag all screens as dirty except the current one.
        This is useful when a screen changes the data models and we
        want to ensure the other screens can find out.
        """

        if not self.registered_screens:
            self.logger.warning("No registered screens to flag as dirty.")
            return

        screens = [s for s in self.registered_screens if s != current_screen]

        if not screens:
            self.logger.debug("No screens to flag as dirty (excluding current).")
            return

        self.flag_screen_dirty(*screens)

    def is_screen_dirty(self, screen_name: str) -> bool:
        """Check if a screen is flagged as dirty."""
        return self.dirty_screens.get(screen_name, False)

    def clear_dirty_screens(self) -> None:
        """Clear all dirty flags."""
        self.logger.debug("Clearing all dirty screens.")
        self.dirty_screens.clear()
