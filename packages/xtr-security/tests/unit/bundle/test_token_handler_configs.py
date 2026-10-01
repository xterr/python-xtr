"""The token-handler configurations validate their fields."""

from __future__ import annotations

import pytest

from xtr_security.bundle import OidcTokenHandlerConfig, ServiceTokenHandlerConfig
from xtr_security.exception import InvalidConfigurationError


class _Handler:
    """A stand-in handler class."""


def test_a_service_handler_needs_a_class() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = ServiceTokenHandlerConfig(service="not-a-class")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # the point of the test


def test_a_service_handler_keeps_its_class_and_qualifier() -> None:
    config = ServiceTokenHandlerConfig(_Handler, qualifier="main")

    assert config.service is _Handler
    assert config.qualifier == "main"
    assert config.type == "id"


def test_an_oidc_handler_keeps_its_fields() -> None:
    config = OidcTokenHandlerConfig(
        issuers=("https://issuer.example",),
        audience="shop-api",
        jwks_uri="https://issuer.example/jwks.json",
        claim="uid",
        leeway=30,
        enforce_at_jwt_type=True,
    )

    assert config.issuers == ("https://issuer.example",)
    assert config.audience == "shop-api"
    assert config.jwks_uri == "https://issuer.example/jwks.json"
    assert config.claim == "uid"
    assert config.leeway == 30
    assert config.enforce_at_jwt_type is True
    assert config.algorithms == ("RS256",)
    assert config.type == "oidc"


def test_an_oidc_handler_needs_at_least_one_issuer() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenHandlerConfig(audience="shop-api", jwks_uri="https://issuer.example/jwks.json")


def test_an_oidc_handler_needs_an_audience() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenHandlerConfig(
            issuers=("https://issuer.example",),
            jwks_uri="https://issuer.example/jwks.json",
        )


def test_an_oidc_handler_needs_a_key_source() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenHandlerConfig(issuers=("https://issuer.example",), audience="shop-api")


def test_an_oidc_handler_refuses_more_than_one_key_source() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenHandlerConfig(
            issuers=("https://issuer.example",),
            audience="shop-api",
            keyset='{"keys": []}',
            jwks_uri="https://issuer.example/jwks.json",
        )
