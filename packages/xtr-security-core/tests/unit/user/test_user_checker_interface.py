"""The user-checker interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.user import ChainUserChecker, InMemoryUserChecker, UserCheckerInterface


def test_the_checkers_satisfy_the_interface() -> None:
    assert isinstance(InMemoryUserChecker(), UserCheckerInterface)
    assert isinstance(ChainUserChecker([]), UserCheckerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), UserCheckerInterface)
