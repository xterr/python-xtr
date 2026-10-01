"""The user-provider interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.user import ChainUserProvider, InMemoryUserProvider, UserProviderInterface


def test_the_providers_satisfy_the_interface() -> None:
    assert isinstance(InMemoryUserProvider(), UserProviderInterface)
    assert isinstance(ChainUserProvider([]), UserProviderInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), UserProviderInterface)
