"""The build helper turns a hasher config into the live hasher it describes."""

from __future__ import annotations

import pytest
from xtr_password_hasher import (
    InvalidArgumentError,
    MigratingPasswordHasher,
    NativePasswordHasher,
    Pbkdf2PasswordHasher,
    PlaintextPasswordHasher,
)
from xtr_password_hasher.hasher.create_auto_password_hasher import bcrypt_available

from xtr_security.bundle import (
    AutoHasherConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    PlaintextHasherConfig,
    ServiceHasherConfig,
)
from xtr_security.bundle._password_hasher_build import build_hasher
from xtr_security.exception import InvalidConfigurationError


class _Service:
    pass


def test_it_builds_a_native_hasher() -> None:
    hasher = build_hasher(
        NativeHasherConfig(algorithm="argon2id", time_cost=1, memory_cost=8, parallelism=1),
    )

    assert isinstance(hasher, NativePasswordHasher)


def test_it_builds_a_pbkdf2_hasher_from_its_settings() -> None:
    config = Pbkdf2HasherConfig(
        hash_algorithm="sha256", encode_as_base64=False, iterations=1, key_length=20
    )

    hasher = build_hasher(config)

    assert isinstance(hasher, Pbkdf2PasswordHasher)
    expected = Pbkdf2PasswordHasher(
        "sha256", encode_hash_as_base64=False, iterations=1, length=20
    ).hash("secret", "salt")
    assert hasher.hash("secret", "salt") == expected


def test_it_builds_a_plaintext_hasher() -> None:
    assert isinstance(build_hasher(PlaintextHasherConfig()), PlaintextPasswordHasher)


def test_it_builds_a_case_insensitive_plaintext_hasher() -> None:
    hasher = build_hasher(PlaintextHasherConfig(ignore_case=True))

    assert hasher.verify("Secret", "sECRET")


def test_a_config_with_migrate_from_becomes_migrating() -> None:
    config = NativeHasherConfig(
        algorithm="argon2id",
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        migrate_from=(Pbkdf2HasherConfig(),),
    )

    assert isinstance(build_hasher(config), MigratingPasswordHasher)


def test_auto_is_a_migrating_hasher_over_argon2id() -> None:
    hasher = build_hasher(AutoHasherConfig())

    assert isinstance(hasher, MigratingPasswordHasher)
    assert hasher.hash("secret").startswith("$argon2id$")


def test_auto_verifies_a_salted_pbkdf2_hash() -> None:
    hasher = build_hasher(AutoHasherConfig())
    legacy = Pbkdf2PasswordHasher().hash("secret", "salt")

    assert isinstance(hasher, MigratingPasswordHasher)
    assert hasher.verify(legacy, "secret", "salt")


def test_auto_verifies_a_bcrypt_hash_when_available() -> None:
    if not bcrypt_available():  # pragma: no cover — the extra is installed in dev
        pytest.skip("bcrypt extra not installed")
    hasher = build_hasher(AutoHasherConfig())
    legacy = NativePasswordHasher("bcrypt", cost=4).hash("secret")

    assert hasher.verify(legacy, "secret")


def test_a_service_config_cannot_be_built_directly() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = build_hasher(ServiceHasherConfig(service=_Service))


def test_a_plaintext_migrate_from_source_is_refused() -> None:
    config = NativeHasherConfig(
        algorithm="argon2id",
        time_cost=1,
        memory_cost=8,
        parallelism=1,
        migrate_from=(PlaintextHasherConfig(),),
    )

    with pytest.raises(InvalidConfigurationError):
        _ = build_hasher(config)
