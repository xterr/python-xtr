"""The default encoder maps a provider's outcome to the decode failure reasons."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.keys import RSA_PRIVATE_PEM, RSA_PUBLIC_PEM
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.encoder.header_aware_jwt_encoder_interface import (
    HeaderAwareJwtEncoderInterface,
)
from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.exception.missing_key_error import MissingKeyError
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

if TYPE_CHECKING:
    from pathlib import Path


def _clock() -> MockClock:
    return MockClock("2024-01-01 00:00:00")


def _encoder(clock: MockClock | None = None, *, ttl: int = 3600) -> DefaultJwtEncoder:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        ttl,
        0,
        clock if clock is not None else _clock(),
    )
    return DefaultJwtEncoder(provider)


def test_it_implements_both_encoder_interfaces() -> None:
    assert isinstance(_encoder(), JwtEncoderInterface)


def _keyless(*extras: str) -> DefaultJwtEncoder:
    provider = JoserfcJwsProvider(
        RawKeyLoader(None, None, None, extras), "RS256", 3600, 0, _clock()
    )
    return DefaultJwtEncoder(provider)


def test_signing_with_no_key_raises_the_missing_key_unwrapped() -> None:
    with pytest.raises(MissingKeyError):
        _ = _keyless().encode({"sub": "ada"})


def test_verifying_with_no_key_at_all_raises_the_missing_key_not_a_decode_failure() -> None:
    token = _encoder().encode({"sub": "ada"})

    with pytest.raises(MissingKeyError):
        _ = _keyless().decode(token)


def test_a_verifier_holding_only_additional_keys_still_verifies(tmp_path: Path) -> None:
    public = tmp_path / "rsa-1.pem"
    _ = public.write_text(RSA_PUBLIC_PEM, encoding="utf-8")
    token = _encoder().encode({"sub": "ada"})

    assert _keyless(str(public)).decode(token)["sub"] == "ada"
    assert isinstance(_encoder(), HeaderAwareJwtEncoderInterface)


def test_a_round_trip_returns_the_claims() -> None:
    encoder = _encoder()
    token = encoder.encode({"sub": "ada"})

    assert encoder.decode(token)["sub"] == "ada"


def test_a_header_is_carried_into_the_token() -> None:
    from joserfc import jws  # noqa: PLC0415

    encoder = _encoder()
    token = encoder.encode({"sub": "ada"}, {"typ": "at+jwt"})

    assert jws.extract_compact(token.encode()).headers().get("typ") == "at+jwt"


def test_a_malformed_token_is_an_invalid_token() -> None:
    with pytest.raises(JwtDecodeFailureError) as info:
        _ = _encoder().decode("nonsense")

    assert info.value.get_reason() == JwtDecodeFailureError.INVALID_TOKEN


def test_an_expired_token_is_an_expired_token() -> None:
    clock = _clock()
    encoder = _encoder(clock, ttl=50)
    token = encoder.encode({"sub": "ada"})
    clock.sleep(100)

    with pytest.raises(JwtDecodeFailureError) as info:
        _ = encoder.decode(token)

    assert info.value.get_reason() == JwtDecodeFailureError.EXPIRED_TOKEN


def test_a_wrong_key_is_an_unverified_token() -> None:
    from tests.support.keys import SECOND_RSA_PRIVATE_PEM  # noqa: PLC0415

    signer = DefaultJwtEncoder(
        JoserfcJwsProvider(RawKeyLoader(SECOND_RSA_PRIVATE_PEM, None), "RS256", 3600, 0, _clock()),
    )
    token = signer.encode({"sub": "ada"})

    with pytest.raises(JwtDecodeFailureError) as info:
        _ = _encoder().decode(token)

    assert info.value.get_reason() == JwtDecodeFailureError.UNVERIFIED_TOKEN


def test_an_unverifiable_expired_token_is_unverified_not_expired_with_no_payload() -> None:
    from tests.support.keys import SECOND_RSA_PRIVATE_PEM  # noqa: PLC0415

    clock = _clock()
    signer = DefaultJwtEncoder(
        JoserfcJwsProvider(RawKeyLoader(SECOND_RSA_PRIVATE_PEM, None), "RS256", 50, 0, clock),
    )
    token = signer.encode({"sub": "ada"})
    clock.sleep(100)

    with pytest.raises(JwtDecodeFailureError) as info:
        _ = _encoder(clock).decode(token)

    assert info.value.get_reason() == JwtDecodeFailureError.UNVERIFIED_TOKEN
    assert info.value.get_payload() is None
