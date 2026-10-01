from __future__ import annotations

import pytest
from typing_extensions import override

from xtr_password_hasher import (
    NativePasswordHasher,
    PasswordHasherFactory,
    PasswordHasherFactoryInterface,
    PlaintextPasswordHasher,
    UnknownPasswordHasherError,
)


def test_it_implements_the_password_hasher_factory_interface() -> None:
    assert PasswordHasherFactoryInterface in PasswordHasherFactory.__mro__


class _User:
    def get_password(self) -> str | None:
        return None


class _AdminUser(_User):
    pass


class _AwareUser:
    def get_password(self) -> str | None:
        return None

    def get_password_hasher_name(self) -> str | None:
        return "custom"


class _UndecidedAwareUser(_AwareUser):
    @override
    def get_password_hasher_name(self) -> str | None:
        return None


def _fast_native() -> NativePasswordHasher:
    return NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)


def test_it_resolves_by_the_user_class() -> None:
    factory = PasswordHasherFactory({_User: _fast_native()})

    hasher = factory.get_password_hasher(_User())

    assert isinstance(hasher, NativePasswordHasher)


def test_it_walks_the_mro_to_a_base_class() -> None:
    factory = PasswordHasherFactory({_User: _fast_native()})

    assert factory.get_password_hasher(_AdminUser()) is factory.get_password_hasher(_User())


def test_it_resolves_by_a_module_class_string_key() -> None:
    key = f"{_User.__module__}:{_User.__qualname__}"
    factory = PasswordHasherFactory({key: PlaintextPasswordHasher()})

    assert isinstance(factory.get_password_hasher(_User()), PlaintextPasswordHasher)


def test_it_resolves_by_a_declared_name() -> None:
    factory = PasswordHasherFactory({"custom": PlaintextPasswordHasher()})

    assert isinstance(factory.get_password_hasher(_AwareUser()), PlaintextPasswordHasher)


def test_a_none_name_falls_back_to_the_class() -> None:
    factory = PasswordHasherFactory({_UndecidedAwareUser: _fast_native()})

    assert isinstance(factory.get_password_hasher(_UndecidedAwareUser()), NativePasswordHasher)


def test_it_resolves_a_class_passed_directly() -> None:
    factory = PasswordHasherFactory({_User: _fast_native()})

    assert isinstance(factory.get_password_hasher(_User), NativePasswordHasher)


def test_it_resolves_an_aware_class_passed_directly() -> None:
    factory = PasswordHasherFactory({_AwareUser: _fast_native()})

    assert isinstance(factory.get_password_hasher(_AwareUser), NativePasswordHasher)


def test_it_resolves_a_name_passed_directly() -> None:
    factory = PasswordHasherFactory({"custom": PlaintextPasswordHasher()})

    assert isinstance(factory.get_password_hasher("custom"), PlaintextPasswordHasher)


def test_the_ready_hasher_value_is_returned_as_is() -> None:
    ready = PlaintextPasswordHasher()
    factory = PasswordHasherFactory({_User: ready})

    assert factory.get_password_hasher(_User()) is ready


def test_the_same_hasher_instance_is_returned_each_time() -> None:
    factory = PasswordHasherFactory({_User: _fast_native()})

    assert factory.get_password_hasher(_User()) is factory.get_password_hasher(_User())


def test_an_unknown_class_raises() -> None:
    factory = PasswordHasherFactory({})

    with pytest.raises(UnknownPasswordHasherError) as caught:
        _ = factory.get_password_hasher(_User())

    assert _User.__qualname__ in caught.value.looked_up


def test_an_unknown_name_raises() -> None:
    factory = PasswordHasherFactory({})

    with pytest.raises(UnknownPasswordHasherError):
        _ = factory.get_password_hasher("missing")
