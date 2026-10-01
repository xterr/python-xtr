from __future__ import annotations

import pytest

from xtr_password_hasher import (
    InvalidArgumentError,
    InvalidPasswordError,
    PlaintextPasswordHasher,
    is_legacy_password_hasher,
)


def test_it_is_a_legacy_hasher() -> None:
    assert is_legacy_password_hasher(PlaintextPasswordHasher())


def test_it_round_trips_a_password() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("secret")

    assert hashed == "secret"
    assert hasher.verify(hashed, "secret")


def test_it_merges_the_salt_in_braces() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("secret", "salt")

    assert hashed == "secret{salt}"
    assert hasher.verify(hashed, "secret", "salt")
    assert not hasher.verify(hashed, "secret")


def test_an_empty_salt_is_no_salt() -> None:
    assert PlaintextPasswordHasher().hash("secret", "") == "secret"


@pytest.mark.parametrize("salt", ["a{b", "a}b"])
def test_it_refuses_a_salt_holding_a_brace(salt: str) -> None:
    hasher = PlaintextPasswordHasher()

    with pytest.raises(InvalidArgumentError):
        _ = hasher.hash("secret", salt)
    with pytest.raises(InvalidArgumentError):
        _ = hasher.verify("secret", "secret", salt)


def test_it_rejects_a_wrong_password() -> None:
    hasher = PlaintextPasswordHasher()

    assert not hasher.verify(hasher.hash("secret"), "nope")


def test_it_compares_case_sensitively_by_default() -> None:
    assert not PlaintextPasswordHasher().verify("Secret", "secret")


def test_it_can_ignore_the_password_case() -> None:
    hasher = PlaintextPasswordHasher(ignore_password_case=True)

    assert hasher.verify("Secret{Salt}", "sECRET", "salt")


def test_it_handles_an_empty_password() -> None:
    hasher = PlaintextPasswordHasher()

    assert hasher.verify(hasher.hash(""), "")


def test_it_round_trips_a_non_ascii_password() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("pässwörd")

    assert hasher.verify(hashed, "pässwörd")
    assert not hasher.verify(hashed, "password")


def test_it_refuses_an_over_long_password() -> None:
    with pytest.raises(InvalidPasswordError):
        _ = PlaintextPasswordHasher().hash("a" * 4097)


def test_verify_returns_false_for_an_over_long_password() -> None:
    assert not PlaintextPasswordHasher().verify("secret", "a" * 4097)


def test_it_never_needs_rehash() -> None:
    hasher = PlaintextPasswordHasher()

    assert not hasher.needs_rehash(hasher.hash("secret"))
