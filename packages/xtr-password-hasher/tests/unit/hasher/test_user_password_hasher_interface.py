from __future__ import annotations

from xtr_password_hasher import (
    PasswordHasherFactory,
    UserPasswordHasher,
    UserPasswordHasherInterface,
)


class _NotUserHasher:
    pass


def test_the_user_hasher_satisfies_it() -> None:
    hasher = UserPasswordHasher(PasswordHasherFactory({}))

    assert isinstance(hasher, UserPasswordHasherInterface)


def test_an_object_missing_the_methods_does_not() -> None:
    assert not isinstance(_NotUserHasher(), UserPasswordHasherInterface)
