"""The equatable interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.user import EquatableInterface, InMemoryUser


def test_an_in_memory_user_satisfies_it() -> None:
    assert isinstance(InMemoryUser("alice"), EquatableInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), EquatableInterface)
