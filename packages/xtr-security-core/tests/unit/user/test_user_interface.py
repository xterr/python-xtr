"""The user interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.user import InMemoryUser, OidcUser, UserInterface


def test_the_users_satisfy_the_interface() -> None:
    assert isinstance(InMemoryUser("alice"), UserInterface)
    assert isinstance(OidcUser({"sub": "alice"}), UserInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), UserInterface)
