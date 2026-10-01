"""The header-aware encoder interface widens the plain encoder contract."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.encoder.header_aware_jwt_encoder_interface import (
    HeaderAwareJwtEncoderInterface,
)
from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def test_it_widens_the_plain_encoder_interface() -> None:
    assert issubclass(HeaderAwareJwtEncoderInterface, JwtEncoderInterface)


def test_the_default_encoder_satisfies_the_interface() -> None:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        3600,
        0,
        MockClock("2024-01-01 00:00:00"),
    )

    assert isinstance(DefaultJwtEncoder(provider), HeaderAwareJwtEncoderInterface)
