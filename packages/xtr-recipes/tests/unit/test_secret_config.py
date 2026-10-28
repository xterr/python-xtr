from __future__ import annotations

import base64
import re

import pytest

from xtr_recipes.exception import InvalidManifestError
from xtr_recipes.secret_config import DEFAULT_BYTES, SecretConfig


def _parse(value: str) -> SecretConfig | None:
    return SecretConfig.parse("xtr-x", "SECRET", value)


def test_a_plain_default_is_no_generator() -> None:
    assert _parse("amqp://localhost") is None


def test_the_bare_generator_takes_every_default() -> None:
    assert _parse("%generate(secret)%") == SecretConfig()


def test_every_argument_is_read() -> None:
    parsed = _parse("%generate(secret, bytes=64, encoding=base64, prefix=whsec_)%")

    assert parsed == SecretConfig(byte_count=64, encoding="base64", prefix="whsec_")


def test_arguments_may_come_in_any_order_and_spacing() -> None:
    parsed = _parse("%generate(secret,encoding=hex ,  bytes = 24)%")

    assert parsed == SecretConfig(byte_count=24, encoding="hex")


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("%generate(password)%", "unknown generator 'password'"),
        ("%generate(secret, length=64)%", "unknown argument 'length'"),
        ("%generate(secret, bytes=32, bytes=64)%", "argument 'bytes' given twice"),
        ("%generate(secret, bytes=8)%", "bytes must be a whole number from 16 to 1024"),
        ("%generate(secret, bytes=2048)%", "bytes must be a whole number from 16 to 1024"),
        ("%generate(secret, bytes=lots)%", "bytes must be a whole number from 16 to 1024"),
        ("%generate(secret, encoding=base32)%", "encoding must be one of base64url, base64, hex"),
        ("%generate(secret, prefix=a b)%", "expected name=value, got 'prefix=a b'"),
        ("%generate(secret, prefix=$x)%", "prefix may hold only letters, digits and _ . : -"),
        ("%generate(secret, bytes)%", "expected name=value, got 'bytes'"),
        ("%generate(secret", "expected %generate(secret, name=value, …)%"),
    ],
)
def test_a_misspelt_generator_names_the_key_and_what_is_wrong(value: str, reason: str) -> None:
    with pytest.raises(InvalidManifestError) as exc:
        _ = _parse(value)

    assert exc.value.key == "env.SECRET"
    assert reason in str(exc.value)


def test_the_default_secret_is_unpadded_base64url_of_its_bytes() -> None:
    secret = SecretConfig().generate()

    assert re.fullmatch(r"[A-Za-z0-9_-]+", secret)
    assert len(base64.urlsafe_b64decode(secret + "=")) == DEFAULT_BYTES


def test_a_base64_secret_is_padded_standard_base64() -> None:
    secret = SecretConfig(byte_count=16, encoding="base64").generate()

    assert len(base64.b64decode(secret, validate=True)) == 16
    assert secret.endswith("==")


def test_a_hex_secret_carries_two_characters_a_byte() -> None:
    secret = SecretConfig(byte_count=20, encoding="hex").generate()

    assert re.fullmatch(r"[0-9a-f]{40}", secret)


def test_a_prefix_is_written_before_the_secret() -> None:
    secret = SecretConfig(encoding="base64", prefix="whsec_").generate()

    assert secret.startswith("whsec_")
    assert len(base64.b64decode(secret.removeprefix("whsec_"), validate=True)) == DEFAULT_BYTES


def test_every_secret_is_new() -> None:
    assert SecretConfig().generate() != SecretConfig().generate()
