"""
Authentication and Security Utilities for Exosphere

This modules contains utilities for managing sudo policies and any form
of AAA that may be encountered at runtime.

So far, our approach to sudo is to use a simple policy system that,
while extensible, currently just allows for two options:

- SKIP: Skip operations that require sudo
- NOPASSWD: Use sudo, assuming the sudoers file is configured with NOPASSWD

Actually handling passwords sanely via prompting crossed too many
boundaries, resulted in leaky abstractions, injection and other horrors
and is therefore not implemented.

Patches welcome, but please keep in mind that it is almost definitely
not worth the effort for the time being.
"""

from collections.abc import Callable
from enum import StrEnum, auto


class SudoPolicy(StrEnum):
    """
    Defines the sudo policy for package manager operations
    """

    SKIP = auto()  # Just skip operations that require sudo
    NOPASSWD = auto()  # Use sudo, assuming sudoers has NOPASSWD configured


def has_sudo_flag(func: Callable) -> bool:
    """
    Helper function to check if a callable requires sudo privileges.
    This checks for the `__requires_sudo` attribute on the function,
    which is set by the `require_sudo` decorator.

    Intended to be used with Provider API methods within Exosphere.

    See also: `require_sudo` decorator in `exosphere.providers.api`

    :param func: The function to check.
    :return: True if the function requires sudo, False otherwise
    """

    if not callable(func):
        raise TypeError(f"Expected a callable, got {type(func).__name__}")

    return getattr(func, "__requires_sudo", False)


def check_sudo_policy(func: Callable, sudo_policy: SudoPolicy) -> bool:
    """
    Check if the function requires sudo and if the current sudo policy allows it.

    :param func: The function to check.
    :param sudo_policy: The current sudo policy.
    :return: True if the function can be executed under the current sudo policy
    """

    if not callable(func):
        raise TypeError(f"Expected a callable, got {type(func).__name__}")

    requires_sudo = has_sudo_flag(func)
    return not requires_sudo or sudo_policy != SudoPolicy.SKIP
