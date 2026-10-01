from __future__ import annotations

import pytest

from xtr_password_hasher import (
    MigratingPasswordHasher,
    NativePasswordHasher,
    Pbkdf2PasswordHasher,
    create_auto_password_hasher,
)
from xtr_password_hasher.hasher.create_auto_password_hasher import bcrypt_available


def test_it_is_a_migrating_hasher_over_argon2id() -> None:
    hasher = create_auto_password_hasher()

    assert isinstance(hasher, MigratingPasswordHasher)
    assert hasher.hash("secret").startswith("$argon2id$")


def test_it_verifies_a_pbkdf2_hash() -> None:
    hasher = create_auto_password_hasher()
    legacy = Pbkdf2PasswordHasher(iterations=1000).hash("secret")

    assert hasher.verify(legacy, "secret")


def test_it_verifies_a_bcrypt_hash_when_available() -> None:
    if not bcrypt_available():  # pragma: no cover — the extra is installed in dev
        pytest.skip("bcrypt extra not installed")
    hasher = create_auto_password_hasher()
    legacy = NativePasswordHasher("bcrypt", cost=4).hash("secret")

    assert hasher.verify(legacy, "secret")
