from __future__ import annotations

from xtr_password_hasher import (
    LegacyPasswordHasherInterface,
    NativePasswordHasher,
    PasswordHasherInterface,
    Pbkdf2PasswordHasher,
    is_legacy_password_hasher,
)


class _StructuralHasher:
    def hash(self, plain_password: str, salt: str | None = None) -> str:
        del salt
        return plain_password

    def verify(self, hashed_password: str, plain_password: str, salt: str | None = None) -> bool:
        del salt
        return hashed_password == plain_password

    def needs_rehash(self, hashed_password: str) -> bool:
        del hashed_password
        return False


def test_it_extends_the_password_hasher_interface() -> None:
    assert issubclass(LegacyPasswordHasherInterface, PasswordHasherInterface)


def test_a_hasher_declaring_it_is_legacy() -> None:
    assert is_legacy_password_hasher(Pbkdf2PasswordHasher())


def test_a_self_salting_hasher_is_not_legacy() -> None:
    hasher = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)

    assert not is_legacy_password_hasher(hasher)


def test_the_shape_alone_does_not_make_a_hasher_legacy() -> None:
    # isinstance cannot tell the two interfaces apart: they share every method name.
    hasher = _StructuralHasher()

    assert isinstance(hasher, LegacyPasswordHasherInterface)
    assert not is_legacy_password_hasher(hasher)
