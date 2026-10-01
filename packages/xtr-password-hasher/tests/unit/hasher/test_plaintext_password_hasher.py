from __future__ import annotations

import pytest

from xtr_password_hasher import (
    InvalidPasswordError,
    PasswordHasherInterface,
    PlaintextPasswordHasher,
)


def test_it_implements_the_password_hasher_interface() -> None:
    assert PasswordHasherInterface in PlaintextPasswordHasher.__mro__


def test_it_round_trips_a_password() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("secret")

    assert hashed == "secret"
    assert hasher.verify(hashed, "secret")


def test_it_rejects_a_wrong_password() -> None:
    hasher = PlaintextPasswordHasher()

    assert not hasher.verify(hasher.hash("secret"), "nope")


def test_it_handles_an_empty_password() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("")

    assert hasher.verify(hashed, "")


def test_it_round_trips_a_non_ascii_password() -> None:
    hasher = PlaintextPasswordHasher()

    hashed = hasher.hash("pässwörd")

    assert hasher.verify(hashed, "pässwörd")
    assert not hasher.verify(hashed, "password")


def test_it_refuses_an_over_long_password() -> None:
    hasher = PlaintextPasswordHasher()

    with pytest.raises(InvalidPasswordError):
        _ = hasher.hash("a" * 4097)


def test_verify_returns_false_for_an_over_long_password() -> None:
    hasher = PlaintextPasswordHasher()

    assert not hasher.verify("secret", "a" * 4097)


def test_it_never_needs_rehash() -> None:
    hasher = PlaintextPasswordHasher()

    assert not hasher.needs_rehash(hasher.hash("secret"))
