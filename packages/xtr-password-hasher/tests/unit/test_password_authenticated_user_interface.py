from __future__ import annotations

from xtr_password_hasher import PasswordAuthenticatedUserInterface


class _User:
    def get_password(self) -> str | None:
        return "hash"


class _NotUser:
    pass


def test_a_user_with_get_password_satisfies_it() -> None:
    assert isinstance(_User(), PasswordAuthenticatedUserInterface)


def test_an_object_without_get_password_does_not() -> None:
    assert not isinstance(_NotUser(), PasswordAuthenticatedUserInterface)
