"""The password-hasher configs carry their discriminator and validate their values."""

from __future__ import annotations

import pytest
from xtr_password_hasher import InvalidArgumentError

from xtr_security.bundle import (
    AutoHasherConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    PlaintextHasherConfig,
    ServiceHasherConfig,
)


class _Service:
    pass


def test_every_config_carries_its_discriminator() -> None:
    assert AutoHasherConfig().type == "auto"
    assert NativeHasherConfig().type == "native"
    assert Pbkdf2HasherConfig().type == "pbkdf2"
    assert PlaintextHasherConfig().type == "plaintext"
    assert ServiceHasherConfig(service=_Service).type == "service"


def test_native_refuses_an_unknown_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativeHasherConfig(algorithm="md5")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_native_refuses_a_bad_bcrypt_cost() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativeHasherConfig(cost=3)


def test_native_refuses_a_non_positive_argon2_cost() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NativeHasherConfig(time_cost=0)


def test_pbkdf2_defaults_match_the_legacy_scheme() -> None:
    config = Pbkdf2HasherConfig()

    assert (config.hash_algorithm, config.encode_as_base64) == ("sha512", True)
    assert (config.iterations, config.key_length) == (1000, 40)


def test_pbkdf2_refuses_no_iterations() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2HasherConfig(iterations=0)


def test_pbkdf2_refuses_a_non_positive_key_length() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2HasherConfig(key_length=0)


@pytest.mark.parametrize("digest", ["not-a-digest", "shake_128"])
def test_pbkdf2_refuses_a_digest_pbkdf2_cannot_run(digest: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Pbkdf2HasherConfig(hash_algorithm=digest)


def test_service_refuses_a_non_class() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = ServiceHasherConfig(service=object())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
