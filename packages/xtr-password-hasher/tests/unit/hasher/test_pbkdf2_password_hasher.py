from __future__ import annotations

import pytest

from xtr_password_hasher import (
    InvalidArgumentError,
    InvalidPasswordError,
    Pbkdf2PasswordHasher,
    is_legacy_password_hasher,
)

# The derived key of "password" under an empty salt, SHA-256, one iteration, 40 bytes — the
# vector other implementations of this scheme are checked against.
_HEX_VECTOR = "c1232f10f62715fda06ae7c0a2037ca19b33cf103b727ba56d870c11f290a2ab106974c75607c8a3"
_BASE64_VECTOR = "wSMvEPYnFf2gaufAogN8oZszzxA7cnulbYcMEfKQoqsQaXTHVgfIow=="


def test_it_is_a_legacy_hasher() -> None:
    assert is_legacy_password_hasher(Pbkdf2PasswordHasher())


def test_it_hashes_to_the_hex_vector() -> None:
    hasher = Pbkdf2PasswordHasher("sha256", encode_hash_as_base64=False, iterations=1, length=40)

    assert hasher.hash("password", "") == _HEX_VECTOR


def test_it_hashes_to_the_base64_vector() -> None:
    hasher = Pbkdf2PasswordHasher("sha256", encode_hash_as_base64=True, iterations=1, length=40)

    assert hasher.hash("password", "") == _BASE64_VECTOR


def test_it_verifies_the_vectors() -> None:
    assert Pbkdf2PasswordHasher(
        "sha256", encode_hash_as_base64=False, iterations=1, length=40
    ).verify(_HEX_VECTOR, "password", "")
    assert Pbkdf2PasswordHasher(
        "sha256", encode_hash_as_base64=True, iterations=1, length=40
    ).verify(_BASE64_VECTOR, "password")


def test_its_defaults_are_sha512_base64_1000_iterations_40_bytes() -> None:
    default = Pbkdf2PasswordHasher().hash("secret", "salt")

    assert default == Pbkdf2PasswordHasher(
        "sha512", encode_hash_as_base64=True, iterations=1000, length=40
    ).hash("secret", "salt")
    assert len(default) == 56


def test_it_round_trips_a_password_under_a_salt() -> None:
    hasher = Pbkdf2PasswordHasher()

    hashed = hasher.hash("secret", "pepper")

    assert hasher.verify(hashed, "secret", "pepper")


def test_the_salt_changes_the_hash() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert hasher.hash("secret", "one") != hasher.hash("secret", "two")
    assert not hasher.verify(hasher.hash("secret", "one"), "secret", "two")


def test_no_salt_is_an_empty_salt() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert hasher.hash("secret") == hasher.hash("secret", "")


def test_it_rejects_a_wrong_password() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert not hasher.verify(hasher.hash("secret", "salt"), "nope", "salt")


def test_it_rejects_a_hash_of_the_wrong_length() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert not hasher.verify(hasher.hash("secret")[:-1], "secret")


def test_it_rejects_a_dollar_delimited_hash_of_the_right_length() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert not hasher.verify("$" * 56, "secret")


def test_it_refuses_an_over_long_password() -> None:
    with pytest.raises(InvalidPasswordError):
        _ = Pbkdf2PasswordHasher().hash("a" * 4097)


def test_verify_returns_false_for_an_over_long_password() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert not hasher.verify(hasher.hash("secret"), "a" * 4097)


def test_it_never_needs_rehash() -> None:
    hasher = Pbkdf2PasswordHasher()

    assert not hasher.needs_rehash(hasher.hash("secret"))


def test_it_refuses_no_iterations() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher(iterations=0)


def test_it_refuses_an_unknown_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher("not-a-digest")


def test_it_refuses_a_non_positive_length() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2PasswordHasher(length=0)
