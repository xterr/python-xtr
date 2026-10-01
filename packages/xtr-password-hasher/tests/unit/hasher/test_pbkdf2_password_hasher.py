from __future__ import annotations

import pytest

from xtr_password_hasher import (
    InvalidArgumentError,
    InvalidPasswordError,
    PasswordHasherInterface,
    Pbkdf2PasswordHasher,
)


def test_it_implements_the_password_hasher_interface() -> None:
    assert PasswordHasherInterface in Pbkdf2PasswordHasher.__mro__


def _fast() -> Pbkdf2PasswordHasher:
    return Pbkdf2PasswordHasher(iterations=1000)


def test_it_round_trips_a_password() -> None:
    hasher = _fast()

    hashed = hasher.hash("secret")

    assert hashed.startswith("$pbkdf2-sha512$1000$")
    assert hasher.verify(hashed, "secret")


def test_it_rejects_a_wrong_password() -> None:
    hasher = _fast()

    assert not hasher.verify(hasher.hash("secret"), "nope")


def test_it_handles_an_empty_password() -> None:
    hasher = _fast()

    assert hasher.verify(hasher.hash(""), "")


def test_two_hashes_of_one_password_differ_by_salt() -> None:
    hasher = _fast()

    assert hasher.hash("secret") != hasher.hash("secret")


def test_it_refuses_an_over_long_password() -> None:
    with pytest.raises(InvalidPasswordError):
        _ = _fast().hash("a" * 4097)


def test_verify_returns_false_for_an_over_long_password() -> None:
    hasher = _fast()

    assert not hasher.verify(hasher.hash("secret"), "a" * 4097)


def test_needs_rehash_when_iterations_change() -> None:
    hashed = _fast().hash("secret")

    assert Pbkdf2PasswordHasher(iterations=2000).needs_rehash(hashed)


def test_no_rehash_when_parameters_match() -> None:
    hasher = _fast()

    assert not hasher.needs_rehash(hasher.hash("secret"))


def test_needs_rehash_on_a_foreign_hash() -> None:
    assert _fast().needs_rehash("$argon2id$v=19$m=8$something")


def test_verify_rejects_a_malformed_hash() -> None:
    hasher = _fast()

    assert not hasher.verify("not-a-pbkdf2-hash", "secret")
    assert not hasher.verify("$pbkdf2-sha512$notanumber$c2FsdA==$aGFzaA==", "secret")


def test_it_refuses_too_few_iterations() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher(iterations=999)


def test_it_refuses_an_unknown_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher(hash_algorithm="not-a-digest")


def test_it_refuses_a_non_positive_key_length() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher(key_length=0)
