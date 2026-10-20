"""The token-handler configurations validate their fields."""

from __future__ import annotations

import pytest

from xtr_security.bundle import (
    Oauth2TokenHandlerConfig,
    OidcTokenHandlerConfig,
    OidcUserInfoTokenHandlerConfig,
    ServiceTokenHandlerConfig,
)
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


def test_an_oidc_handler_refuses_a_leeway_over_the_cap() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcTokenHandlerConfig(
            issuers=("https://issuer.example",),
            audience="shop-api",
            keyset='{"keys": []}',
            leeway=301,
        )


def test_an_oidc_handler_accepts_a_leeway_at_the_cap() -> None:
    config = OidcTokenHandlerConfig(
        issuers=("https://issuer.example",),
        audience="shop-api",
        keyset='{"keys": []}',
        leeway=300,
    )

    assert config.leeway == 300


def test_an_oauth2_handler_needs_an_endpoint() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = Oauth2TokenHandlerConfig()


def test_an_oauth2_handler_refuses_credentials_beside_a_client_service() -> None:
    class _Client:
        """A stand-in client service class."""

    with pytest.raises(InvalidConfigurationError):
        _ = Oauth2TokenHandlerConfig(
            client=_Client,
            credentials="shop:secret",
        )


def test_an_oauth2_handler_refuses_a_discovery_cache_without_an_issuer() -> None:
    class _Cache:
        """A stand-in cache service class."""

    with pytest.raises(InvalidConfigurationError):
        _ = Oauth2TokenHandlerConfig(
            introspection_base_uri="https://as.example/introspect",
            signed_response_discovery_cache=_Cache,
        )


def test_an_oauth2_handler_keeps_its_fields() -> None:
    class _Cache:
        """A stand-in cache service class."""

    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        credentials=("shop", "secret"),
        audiences=("shop-api",),
        issuer="https://as.example",
        claim="sub",
        allowed_time_drift=5,
        cache=_Cache,
        cache_key_prefix="shop",
        cache_ttl=30,
        signed_response_algorithms=("RS256",),
        signed_response_keyset='{"keys": []}',
        signed_response_enforce=False,
        signed_response_discovery_cache=_Cache,
        signed_response_discovery_cache_key="metadata",
    )

    assert config.type == "oauth2"
    assert config.introspection_base_uri == "https://as.example/introspect"
    assert config.credentials == ("shop", "secret")
    assert config.audiences == ("shop-api",)
    assert config.issuer == "https://as.example"
    assert config.claim == "sub"
    assert config.allowed_time_drift == 5
    assert config.cache is _Cache
    assert config.cache_key_prefix == "shop"
    assert config.cache_ttl == 30
    assert config.signed_response_algorithms == ("RS256",)
    assert config.signed_response_keyset == '{"keys": []}'
    assert config.signed_response_enforce is False
    assert config.signed_response_discovery_cache is _Cache
    assert config.signed_response_discovery_cache_key == "metadata"


def test_a_userinfo_handler_needs_an_endpoint() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcUserInfoTokenHandlerConfig()


def test_a_userinfo_handler_refuses_a_discovery_cache_without_a_key() -> None:
    class _Cache:
        """A stand-in cache service class."""

    with pytest.raises(InvalidConfigurationError):
        _ = OidcUserInfoTokenHandlerConfig(
            userinfo_base_uri="https://as.example/userinfo",
            discovery_cache=_Cache,
        )


def test_a_userinfo_handler_keeps_its_fields() -> None:
    config = OidcUserInfoTokenHandlerConfig(
        userinfo_base_uri="https://as.example/userinfo",
        claim="preferred_username",
    )

    assert config.type == "oidc_user_info"
    assert config.claim == "preferred_username"
    assert config.discovery_cache is None
    assert config.discovery_cache_key is None
