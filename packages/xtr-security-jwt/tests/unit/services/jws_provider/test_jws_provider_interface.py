"""The JWS-provider interface is runtime-checkable against the real provider."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def test_the_real_provider_satisfies_the_interface() -> None:
    clock = MockClock("2024-01-01 00:00:00")
    provider = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "RS256", 3600, 0, clock)

    assert isinstance(provider, JwsProviderInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), JwsProviderInterface)
