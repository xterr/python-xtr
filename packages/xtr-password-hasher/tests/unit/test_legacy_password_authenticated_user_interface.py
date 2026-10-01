from __future__ import annotations

from xtr_password_hasher import (
    LegacyPasswordAuthenticatedUserInterface,
    PasswordAuthenticatedUserInterface,
)


class _LegacyUser:
    def get_password(self) -> str | None:
        return "hash"

    def get_salt(self) -> str | None:
        return "salt"


class _User:
    def get_password(self) -> str | None:
        return "hash"


def test_it_extends_the_password_authenticated_user_interface() -> None:
    assert issubclass(LegacyPasswordAuthenticatedUserInterface, PasswordAuthenticatedUserInterface)


def test_a_user_with_get_salt_satisfies_it() -> None:
    assert isinstance(_LegacyUser(), LegacyPasswordAuthenticatedUserInterface)


def test_a_user_without_get_salt_does_not() -> None:
    assert not isinstance(_User(), LegacyPasswordAuthenticatedUserInterface)
