from __future__ import annotations

from xtr_password_hasher import (
    MAX_PASSWORD_LENGTH,
    NativePasswordHasher,
    PasswordHasherInterface,
)


def test_the_shared_length_limit_is_4096() -> None:
    assert MAX_PASSWORD_LENGTH == 4096


def test_a_hasher_satisfies_the_runtime_checkable_protocol() -> None:
    hasher = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)

    assert isinstance(hasher, PasswordHasherInterface)
