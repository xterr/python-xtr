"""The token-manager interface is runtime-checkable against the real manager."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.fakes import RecordingDispatcher
from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def test_the_real_manager_satisfies_the_interface() -> None:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        3600,
        0,
        MockClock("2024-01-01 00:00:00"),
    )
    manager = JwtManager(DefaultJwtEncoder(provider), RecordingDispatcher(), "username")

    assert isinstance(manager, JwtTokenManagerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), JwtTokenManagerInterface)
