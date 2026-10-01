"""The joserfc JWS provider signs, verifies, and judges times as the reference does."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_security_core.exception import InvalidArgumentError

from tests.support.keys import (
    HMAC_SECRET,
    RSA_PRIVATE_PEM,
    RSA_PUBLIC_PEM,
    SECOND_RSA_PRIVATE_PEM,
    SECOND_RSA_PUBLIC_PEM,
)
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader


def _clock() -> MockClock:
    return MockClock("2024-01-01 00:00:00")


def _provider(**kwargs: object) -> JoserfcJwsProvider:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)
    ttl = kwargs.get("ttl", 3600)
    skew = kwargs.get("clock_skew", 0)
    allow = kwargs.get("allow_no_expiration", False)
    return JoserfcJwsProvider(
        loader,
        "RS256",
        ttl if isinstance(ttl, int) else 3600,
        skew if isinstance(skew, int) else 0,
        _clock(),
        allow_no_expiration=bool(allow),
    )


def test_it_implements_the_provider_interface() -> None:
    assert isinstance(_provider(), JwsProviderInterface)


def test_it_signs_and_the_token_is_signed() -> None:
    created = _provider().create({"sub": "ada"})

    assert created.is_signed() is True
    assert created.get_token().count(".") == 2


def test_it_stamps_iat_and_exp_from_the_ttl() -> None:
    now = int(_clock().now().timestamp())
    token = _provider(ttl=100).create({"sub": "ada"}).get_token()
    loaded = _provider(ttl=100).load(token)

    assert loaded.get_payload()["iat"] == now
    assert loaded.get_payload()["exp"] == now + 100


def test_it_keeps_a_payload_iat_and_exp() -> None:
    token = _provider().create({"sub": "ada", "iat": 10, "exp": 20}).get_token()
    loaded = _provider().load(token)

    assert loaded.get_payload()["iat"] == 10
    assert loaded.get_payload()["exp"] == 20


def test_a_round_trip_verifies() -> None:
    token = _provider().create({"sub": "ada"}).get_token()
    loaded = _provider().load(token)

    assert loaded.is_verified() is True
    assert loaded.get_payload()["sub"] == "ada"


def test_a_tampered_token_does_not_verify() -> None:
    token = _provider().create({"sub": "ada"}).get_token()
    loaded = _provider().load(token[:-3] + "aaa")

    assert loaded.is_verified() is False


def test_a_token_from_another_key_does_not_verify() -> None:
    other = JoserfcJwsProvider(
        RawKeyLoader(SECOND_RSA_PRIVATE_PEM, None), "RS256", 3600, 0, _clock()
    )
    token = other.create({"sub": "ada"}).get_token()
    loaded = _provider().load(token)

    assert loaded.is_verified() is False


def test_an_additional_public_key_verifies_a_rotated_token(tmp_path: object) -> None:
    from pathlib import Path  # noqa: PLC0415

    directory = tmp_path if isinstance(tmp_path, Path) else Path(str(tmp_path))
    extra = directory / "old.pem"
    _ = extra.write_text(SECOND_RSA_PUBLIC_PEM, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, RSA_PUBLIC_PEM, None, (str(extra),))
    provider = JoserfcJwsProvider(loader, "RS256", 3600, 0, _clock())
    old = JoserfcJwsProvider(RawKeyLoader(SECOND_RSA_PRIVATE_PEM, None), "RS256", 3600, 0, _clock())
    token = old.create({"sub": "ada"}).get_token()

    assert provider.load(token).is_verified() is True


def test_a_malformed_token_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _provider().load("not-a-token")


def test_it_refuses_an_unsupported_algorithm() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JoserfcJwsProvider(RawKeyLoader(RSA_PRIVATE_PEM, None), "none", 3600, 0, _clock())


def test_it_signs_and_verifies_with_a_shared_secret() -> None:
    loader = RawKeyLoader(HMAC_SECRET, None)
    provider = JoserfcJwsProvider(loader, "HS256", 3600, 0, _clock())
    token = provider.create({"sub": "ada"}).get_token()

    assert provider.load(token).is_verified() is True


def test_no_ttl_and_no_exp_mints_a_token_without_expiry() -> None:
    provider = JoserfcJwsProvider(
        RawKeyLoader(RSA_PRIVATE_PEM, None),
        "RS256",
        None,
        0,
        _clock(),
        allow_no_expiration=True,
    )
    token = provider.create({"sub": "ada"}).get_token()
    loaded = provider.load(token)

    assert "exp" not in loaded.get_payload()
    assert loaded.is_invalid() is False
