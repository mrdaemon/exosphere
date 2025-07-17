import pytest

from exosphere.providers.api import requires_sudo
from exosphere.security import SudoPolicy, check_sudo_policy, has_sudo_flag


def test_requires_sudo_decorator():
    """
    Test that the requires_sudo decorator sets the __requires_sudo attribute.
    """

    @requires_sudo
    def test_func():
        pass

    assert hasattr(test_func, "__requires_sudo")


def test_has_sudo_flag():
    """
    Test that the has_sudo_flag function correctly identifies functions
    that require sudo privileges.
    """

    @requires_sudo
    def test_func():
        pass

    def test_func_no_sudo():
        pass

    assert has_sudo_flag(test_func) is True
    assert has_sudo_flag(test_func_no_sudo) is False


def test_has_sudo_flag_with_invalid_input():
    """
    Test that has_sudo_flag handles non-callable inputs correctly.
    """

    with pytest.raises(TypeError):
        has_sudo_flag("Definitely not a callable")  # type: ignore


@pytest.mark.parametrize(
    "sudo_policy, expected",
    [
        (SudoPolicy.SKIP, False),
        (SudoPolicy.NOPASSWD, True),
    ],
)
def test_check_sudo_policy(sudo_policy, expected):
    """
    Test the check_sudo_policy function.
    """

    @requires_sudo
    def test_func():
        pass

    def test_func_no_sudo():
        pass

    # Test baseline
    assert check_sudo_policy(test_func_no_sudo, sudo_policy) is True

    # Test with sudo required
    assert check_sudo_policy(test_func, sudo_policy) is expected


@pytest.mark.parametrize(
    "sudo_policy, expected",
    [
        (SudoPolicy.SKIP, False),
        (SudoPolicy.NOPASSWD, True),
    ],
)
def test_check_sudo_policy_with_method(sudo_policy, expected):
    """
    Test that check_sudo_policy works with methods that require sudo.
    """

    class TestClass:
        @requires_sudo
        def test_method(self):
            pass

        def test_method_no_sudo(self):
            pass

    instance = TestClass()

    # Test baseline
    assert check_sudo_policy(instance.test_method_no_sudo, sudo_policy) is True

    assert check_sudo_policy(instance.test_method, sudo_policy) is expected


def test_check_sudo_policy_with_invalid_input():
    """
    Test that check_sudo_policy handles non-callable inputs correctly.
    """

    with pytest.raises(TypeError):
        check_sudo_policy("Definitely not a callable", SudoPolicy.SKIP)  # type: ignore
