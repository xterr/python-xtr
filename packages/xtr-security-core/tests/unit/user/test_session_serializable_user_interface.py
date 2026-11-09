"""The user a session can keep whole is a user, found by its inheritance."""

from __future__ import annotations

import inspect

from xtr_security_core.user import (
    InMemoryUser,
    OidcUser,
    SessionSerializableUserInterface,
    UserInterface,
)


def test_it_is_a_user() -> None:
    assert UserInterface in inspect.getmro(SessionSerializableUserInterface)


def test_the_users_a_session_keeps_whole_inherit_it() -> None:
    for user_class in (InMemoryUser, OidcUser):
        assert SessionSerializableUserInterface in user_class.__mro__


def test_an_in_memory_user_satisfies_it() -> None:
    assert isinstance(InMemoryUser("alice"), SessionSerializableUserInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), SessionSerializableUserInterface)
