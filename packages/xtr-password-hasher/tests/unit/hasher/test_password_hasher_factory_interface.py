from __future__ import annotations

from xtr_password_hasher import (
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    PlaintextPasswordHasher,
)


class _NotFactory:
    pass


def test_the_factory_satisfies_it() -> None:
    factory = PasswordHasherFactory({"x": PlaintextPasswordHasher()})

    assert isinstance(factory, PasswordHasherFactoryInterface)


def test_an_object_without_get_password_hasher_does_not() -> None:
    assert not isinstance(_NotFactory(), PasswordHasherFactoryInterface)
