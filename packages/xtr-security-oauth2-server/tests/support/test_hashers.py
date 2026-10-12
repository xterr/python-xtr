"""The recording hasher verifies what it hashed and asks for a stale hash back."""

from __future__ import annotations

from xtr_password_hasher import PasswordHasherInterface

from tests.support.hashers import RecordingPasswordHasher


def test_it_satisfies_the_hasher_contract() -> None:
    assert isinstance(RecordingPasswordHasher(), PasswordHasherInterface)


def test_it_verifies_a_hash_it_made() -> None:
    hasher = RecordingPasswordHasher()

    assert hasher.verify(hasher.hash("s3cret"), "s3cret")


def test_it_refuses_another_password() -> None:
    hasher = RecordingPasswordHasher()

    assert not hasher.verify(hasher.hash("s3cret"), "wrong")


def test_it_verifies_a_hash_made_under_the_stale_prefix() -> None:
    hasher = RecordingPasswordHasher()

    assert hasher.verify("v1$s3cret", "s3cret")


def test_it_refuses_a_hash_made_by_an_unknown_hasher() -> None:
    hasher = RecordingPasswordHasher()

    assert not hasher.verify("md5$s3cret", "s3cret")


def test_it_asks_for_a_rehash_of_a_stale_hash_only() -> None:
    hasher = RecordingPasswordHasher()

    assert hasher.needs_rehash("v1$s3cret")
    assert not hasher.needs_rehash("v2$s3cret")


def test_it_counts_the_hashes_and_the_verifies_it_made() -> None:
    hasher = RecordingPasswordHasher()

    _ = hasher.verify(hasher.hash("s3cret"), "s3cret")

    assert (hasher.hash_calls, hasher.verify_calls) == (1, 1)
