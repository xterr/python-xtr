from __future__ import annotations

from xtr_password_hasher import (
    MigratingPasswordHasher,
    NativePasswordHasher,
    PasswordHasherInterface,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
)


def test_it_implements_the_password_hasher_interface() -> None:
    assert PasswordHasherInterface in MigratingPasswordHasher.__mro__


def _migrating() -> MigratingPasswordHasher:
    best = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)
    return MigratingPasswordHasher(best, Pbkdf2PasswordHasher(iterations=1000))


def test_it_hashes_with_the_best_hasher() -> None:
    hasher = _migrating()

    assert hasher.hash("secret").startswith("$argon2id$")


def test_it_verifies_a_best_hash() -> None:
    hasher = _migrating()

    assert hasher.verify(hasher.hash("secret"), "secret")


def test_it_verifies_a_legacy_hash_through_an_extra() -> None:
    legacy = Pbkdf2PasswordHasher(iterations=1000).hash("secret")

    assert _migrating().verify(legacy, "secret")


def test_it_rejects_a_wrong_password_against_a_legacy_hash() -> None:
    legacy = Pbkdf2PasswordHasher(iterations=1000).hash("secret")

    assert not _migrating().verify(legacy, "nope")


def test_a_best_hash_is_only_tried_against_the_best() -> None:
    # A plaintext extra would "verify" anything equal to the stored string; a
    # best (argon2) hash never reaches it, so the plaintext extra cannot match.
    best = NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)
    hasher = MigratingPasswordHasher(best, PlaintextPasswordHasher())
    hashed = hasher.hash("secret")

    assert not hasher.verify(hashed, hashed)
    assert hasher.verify(hashed, "secret")


def test_needs_rehash_delegates_to_the_best() -> None:
    hasher = _migrating()
    legacy = Pbkdf2PasswordHasher(iterations=1000).hash("secret")

    assert hasher.needs_rehash(legacy)
    assert not hasher.needs_rehash(hasher.hash("secret"))
