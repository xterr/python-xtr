from __future__ import annotations

from xtr_password_hasher import (
    MigratingPasswordHasher,
    NativePasswordHasher,
    PasswordHasherInterface,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
    is_legacy_password_hasher,
)
from xtr_password_hasher.hasher.migrating_password_hasher import hash_with_salt, verify_with_salt


def _argon2() -> NativePasswordHasher:
    return NativePasswordHasher("argon2id", time_cost=1, memory_cost=8, parallelism=1)


def _migrating() -> MigratingPasswordHasher:
    return MigratingPasswordHasher(_argon2(), Pbkdf2PasswordHasher())


def test_it_implements_the_password_hasher_interface() -> None:
    assert PasswordHasherInterface in MigratingPasswordHasher.__mro__


def test_it_is_not_a_legacy_hasher() -> None:
    assert not is_legacy_password_hasher(_migrating())


def test_it_hashes_with_the_best_hasher() -> None:
    assert _migrating().hash("secret").startswith("$argon2id$")


def test_it_ignores_a_salt_the_best_hasher_does_not_take() -> None:
    hasher = _migrating()

    hashed = hasher.hash("secret", "salt")

    assert hashed.startswith("$argon2id$")
    assert hasher.verify(hashed, "secret")


def test_it_hands_the_salt_to_a_legacy_best_hasher() -> None:
    hasher = MigratingPasswordHasher(Pbkdf2PasswordHasher())

    assert hasher.hash("secret", "salt") == Pbkdf2PasswordHasher().hash("secret", "salt")


def test_it_verifies_a_best_hash() -> None:
    hasher = _migrating()

    assert hasher.verify(hasher.hash("secret"), "secret")


def test_it_verifies_a_salted_legacy_hash_through_an_extra() -> None:
    legacy = Pbkdf2PasswordHasher().hash("secret", "salt")

    assert _migrating().verify(legacy, "secret", "salt")
    assert not _migrating().verify(legacy, "secret")


def test_it_rejects_a_wrong_password_against_a_legacy_hash() -> None:
    legacy = Pbkdf2PasswordHasher().hash("secret", "salt")

    assert not _migrating().verify(legacy, "nope", "salt")


def test_a_nested_migrating_hasher_receives_the_salt() -> None:
    legacy = Pbkdf2PasswordHasher().hash("secret", "salt")
    hasher = MigratingPasswordHasher(_argon2(), _migrating())

    assert hasher.verify(legacy, "secret", "salt")


def test_a_best_hash_is_only_tried_against_the_best() -> None:
    # A plaintext extra would "verify" anything equal to the stored string; a
    # best (argon2) hash never reaches it, so the plaintext extra cannot match.
    hasher = MigratingPasswordHasher(_argon2(), PlaintextPasswordHasher())
    hashed = hasher.hash("secret")

    assert not hasher.verify(hashed, hashed)
    assert hasher.verify(hashed, "secret")


def test_needs_rehash_delegates_to_the_best() -> None:
    hasher = _migrating()
    legacy = Pbkdf2PasswordHasher().hash("secret", "salt")

    assert hasher.needs_rehash(legacy)
    assert not hasher.needs_rehash(hasher.hash("secret"))


def test_the_salt_helpers_leave_a_self_salting_hasher_without_one() -> None:
    hasher = _argon2()

    hashed = hash_with_salt(hasher, "secret", "salt")

    assert verify_with_salt(hasher, hashed, "secret", "other")


def test_the_salt_helpers_hand_a_legacy_hasher_its_salt() -> None:
    hasher = PlaintextPasswordHasher()

    assert hash_with_salt(hasher, "secret", "salt") == "secret{salt}"
    assert verify_with_salt(hasher, "secret{salt}", "secret", "salt")
