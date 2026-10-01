from __future__ import annotations

import sys
import types

import argon2
import bcrypt
import pytest
from pwdlib.exceptions import HasherNotAvailable

from xtr_password_hasher import (
    InvalidArgumentError,
    InvalidPasswordError,
    NativePasswordHasher,
    PasswordHasherInterface,
)


def test_it_implements_the_password_hasher_interface() -> None:
    assert PasswordHasherInterface in NativePasswordHasher.__mro__


def _argon2() -> NativePasswordHasher:
    return NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)


def _bcrypt() -> NativePasswordHasher:
    return NativePasswordHasher("bcrypt", cost=4)


def test_argon2_round_trips_a_password() -> None:
    hasher = _argon2()

    hashed = hasher.hash("secret")

    assert hashed.startswith("$argon2id$")
    assert hasher.verify(hashed, "secret")


def test_argon2_rejects_a_wrong_password() -> None:
    hasher = _argon2()

    assert not hasher.verify(hasher.hash("secret"), "nope")


def test_argon2_handles_an_empty_password() -> None:
    hasher = _argon2()

    assert hasher.verify(hasher.hash(""), "")


def test_argon2_refuses_an_over_long_password() -> None:
    with pytest.raises(InvalidPasswordError):
        _ = _argon2().hash("a" * 4097)


def test_argon2_verify_returns_false_for_an_over_long_password() -> None:
    hasher = _argon2()

    assert not hasher.verify(hasher.hash("secret"), "a" * 4097)


def test_argon2_needs_rehash_when_cost_increases() -> None:
    weak = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)
    strong = NativePasswordHasher("argon2id", time_cost=3, memory_cost=64, parallelism=1)

    assert strong.needs_rehash(weak.hash("secret"))


def test_argon2_does_not_need_rehash_at_its_own_cost() -> None:
    hasher = _argon2()

    assert not hasher.needs_rehash(hasher.hash("secret"))


def test_argon2_verifies_a_hash_produced_by_argon2_cffi() -> None:
    foreign = argon2.PasswordHasher().hash("secret")

    assert _argon2().verify(foreign, "secret")


def test_bcrypt_round_trips_a_password() -> None:
    hasher = _bcrypt()

    hashed = hasher.hash("secret")

    assert hashed.startswith("$2b$")
    assert hasher.verify(hashed, "secret")


def test_bcrypt_handles_a_password_over_72_bytes() -> None:
    hasher = _bcrypt()
    plain = "a" * 100

    hashed = hasher.hash(plain)

    assert hasher.verify(hashed, plain)


def test_bcrypt_long_passwords_are_stable() -> None:
    hasher = _bcrypt()
    hashed = hasher.hash("a" * 100)

    assert hasher.verify(hashed, "a" * 100)
    assert not hasher.verify(hashed, "b" * 100)


def test_bcrypt_verifies_a_2y_hash_from_another_stack() -> None:
    foreign = bcrypt.hashpw(b"secret", bcrypt.gensalt(4, prefix=b"2b")).replace(b"2b", b"2y")

    assert _bcrypt().verify(foreign.decode(), "secret")


def test_argon2_reports_a_bcrypt_hash_as_needing_rehash() -> None:
    bcrypt_hash = _bcrypt().hash("secret")

    assert _argon2().needs_rehash(bcrypt_hash)


def test_argon2_can_verify_a_bcrypt_hash_when_the_backend_is_present() -> None:
    bcrypt_hash = _bcrypt().hash("secret")

    assert _argon2().verify(bcrypt_hash, "secret")


def test_verify_of_an_unrecognised_hash_is_false() -> None:
    assert not _argon2().verify("$pbkdf2-sha512$1000$c2FsdA==$aGFzaA==", "secret")


def test_needs_rehash_on_an_unrecognised_hash() -> None:
    assert _argon2().needs_rehash("$pbkdf2-sha512$1000$c2FsdA==$aGFzaA==")


def test_it_refuses_an_unknown_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativePasswordHasher("md5")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_it_refuses_a_bcrypt_cost_out_of_range() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativePasswordHasher("bcrypt", cost=3)
    with pytest.raises(InvalidArgumentError):
        _ = NativePasswordHasher("bcrypt", cost=32)


def test_it_refuses_a_non_positive_argon2_cost() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativePasswordHasher("argon2id", time_cost=0)


def test_argon2_builds_when_the_bcrypt_backend_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = types.ModuleType("pwdlib.hashers.bcrypt")

    def _raise(name: str) -> object:
        raise HasherNotAvailable(name)

    setattr(fake, "__getattr__", _raise)  # PEP 562 module __getattr__  # noqa: B010
    monkeypatch.setitem(sys.modules, "pwdlib.hashers.bcrypt", fake)

    hasher = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)

    assert hasher.verify(hasher.hash("secret"), "secret")
