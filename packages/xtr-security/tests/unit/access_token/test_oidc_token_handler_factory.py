"""The OIDC token-handler factory builds a handler that verifies a real token."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey

from xtr_security.bundle import (
    OidcTokenHandlerConfig,
    OidcTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceKey

    from xtr_security.access_token.oidc_token_handler_factory import _AsyncCloseable


def _key() -> RSAKey:
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


def _jwks(key: RSAKey) -> str:
    return json.dumps(KeySet([key]).as_dict(private=False))


@final
class _Recorder:
    """A stand-in service configurator recording the registered factory."""

    factory: Callable[[], object] | None
    qualifier: str | None

    def __init__(self) -> None:
        self.factory = None
        self.qualifier = None

    def set(self, factory: object, *, qualifier: str | None = None) -> _Recorder:
        self.factory = cast("Callable[[], object]", factory)
        self.qualifier = qualifier
        return self

    @property
    def key(self) -> ServiceKey:
        return cast("ServiceKey", (object, self.qualifier))


def test_it_carries_its_interface_key_and_config() -> None:
    factory = OidcTokenHandlerFactory()

    assert TokenHandlerFactoryInterface in type(factory).__mro__
    assert factory.key == "oidc"
    assert factory.config_type is OidcTokenHandlerConfig


@pytest.mark.anyio
async def test_it_builds_a_handler_that_verifies_a_token() -> None:
    key = _key()
    config = OidcTokenHandlerConfig(
        issuers=("https://issuer.example",),
        audience="shop-api",
        keyset=_jwks(key),
    )
    recorder = _Recorder()

    _ = OidcTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oidc",
        config,
    )
    assert recorder.factory is not None
    handler: object = recorder.factory()

    from xtr_security_http.access_token.oidc import OidcTokenHandler

    assert isinstance(handler, OidcTokenHandler)

    token = jwt.encode(
        {"alg": "RS256", "kid": "k1"},
        {
            "iss": "https://issuer.example",
            "aud": "shop-api",
            "sub": "alice",
            "iat": 0,
            "exp": 9_999_999_999,
        },
        key,
    )
    badge = await handler.get_user_badge_from(token)

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_it_builds_a_discovery_backed_handler() -> None:
    config = OidcTokenHandlerConfig(
        issuers=("https://issuer.example",),
        audience="shop-api",
        discovery_uri="https://issuer.example",
    )
    recorder = _Recorder()

    _ = OidcTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oidc",
        config,
    )
    assert recorder.factory is not None
    handler: object = recorder.factory()

    from xtr_security_http.access_token.oidc import OidcTokenHandler

    assert isinstance(handler, OidcTokenHandler)


def _discovery_config() -> OidcTokenHandlerConfig:
    return OidcTokenHandlerConfig(
        issuers=("https://issuer.example",),
        audience="shop-api",
        discovery_uri="https://issuer.example",
    )


def _build_one(factory: OidcTokenHandlerFactory, service_id: str, config: object) -> None:
    """Register the handler under ``service_id`` and build it once."""
    recorder = _Recorder()
    _ = factory.create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        service_id,
        config,
    )
    assert recorder.factory is not None
    _ = recorder.factory()


def test_with_closeables_collects_every_discovery_provider_it_builds() -> None:
    from xtr_security_http.access_token.oidc import DiscoveryOidcKeySetProvider

    sink: list[_AsyncCloseable] = []
    factory = OidcTokenHandlerFactory().with_closeables(sink)

    _build_one(factory, "api_oidc", _discovery_config())
    _build_one(factory, "admin_oidc", _discovery_config())

    assert len(sink) == 2
    assert all(isinstance(provider, DiscoveryOidcKeySetProvider) for provider in sink)


def test_a_static_key_set_provider_is_not_collected() -> None:
    sink: list[_AsyncCloseable] = []
    factory = OidcTokenHandlerFactory().with_closeables(sink)

    _build_one(
        factory,
        "api_oidc",
        OidcTokenHandlerConfig(
            issuers=("https://issuer.example",),
            audience="shop-api",
            keyset=_jwks(_key()),
        ),
    )

    assert sink == []


def test_the_discovery_client_carries_an_explicit_timeout_and_connection_limit() -> None:
    import httpx
    from xtr_security_http.access_token.oidc import DiscoveryOidcKeySetProvider

    from xtr_security.access_token.oidc_token_handler_factory import (
        _DISCOVERY_MAX_CONNECTIONS,
        _DISCOVERY_TIMEOUT,
    )

    sink: list[_AsyncCloseable] = []
    factory = OidcTokenHandlerFactory().with_closeables(sink)
    _build_one(factory, "api_oidc", _discovery_config())
    provider = cast("DiscoveryOidcKeySetProvider", sink[0])

    client = provider._http_client_factory()
    transport = client._transport
    assert isinstance(transport, httpx.AsyncHTTPTransport)
    # The pool is the only place the limits survive; a proxy pool has no such
    # attribute, so the default makes the assertion fail rather than pass blind.
    max_connections = getattr(transport._pool, "_max_connections", 0)

    assert client.timeout == httpx.Timeout(_DISCOVERY_TIMEOUT)
    # Equality with the constant alone would hold even if the factory passed no
    # timeout at all, as long as the constant happened to match the library
    # default. The second assertion is what proves the factory chose.
    assert client.timeout != httpx.AsyncClient().timeout
    assert max_connections == _DISCOVERY_MAX_CONNECTIONS
