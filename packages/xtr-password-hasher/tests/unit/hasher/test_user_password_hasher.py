from __future__ import annotations

from typing import final

from xtr_password_hasher import (
    NativePasswordHasher,
    PasswordHasherFactory,
    UserPasswordHasher,
    UserPasswordHasherInterface,
)


def test_it_implements_the_user_password_hasher_interface() -> None:
    assert UserPasswordHasherInterface in UserPasswordHasher.__mro__


@final
class _User:
    def __init__(self, password: str | None) -> None:
        self._password = password

    def get_password(self) -> str | None:
        return self._password


def _hasher() -> UserPasswordHasher:
    hasher = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)
    return UserPasswordHasher(PasswordHasherFactory({_User: hasher}))


def test_it_hashes_a_password_for_a_user() -> None:
    hasher = _hasher()

    hashed = hasher.hash_password(_User(None), "secret")

    assert hashed.startswith("$argon2id$")


def test_a_valid_password_is_accepted() -> None:
    hasher = _hasher()
    hashed = hasher.hash_password(_User(None), "secret")

    assert hasher.is_password_valid(_User(hashed), "secret")


def test_a_wrong_password_is_rejected() -> None:
    hasher = _hasher()
    hashed = hasher.hash_password(_User(None), "secret")

    assert not hasher.is_password_valid(_User(hashed), "nope")


def test_a_user_without_a_password_is_never_valid() -> None:
    hasher = _hasher()

    assert not hasher.is_password_valid(_User(None), "secret")


def test_a_user_without_a_password_never_needs_rehash() -> None:
    hasher = _hasher()

    assert not hasher.needs_rehash(_User(None))


def test_needs_rehash_reflects_the_stored_hash() -> None:
    weak = UserPasswordHasher(
        PasswordHasherFactory(
            {_User: NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)},
        ),
    )
    strong = UserPasswordHasher(
        PasswordHasherFactory(
            {_User: NativePasswordHasher("argon2id", time_cost=3, memory_cost=64, parallelism=1)},
        ),
    )
    hashed = weak.hash_password(_User(None), "secret")

    assert strong.needs_rehash(_User(hashed))
    assert not weak.needs_rehash(_User(hashed))
