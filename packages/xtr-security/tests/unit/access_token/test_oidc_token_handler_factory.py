"""The OIDC token-handler factory builds a handler that verifies a real token."""

from __future__ import annotations

import json
from types import FunctionType
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
    """A stand-in service configurator recording every registered factory.

    ``factory`` is the last one registered: the handler, which the factory
    registers after the HTTP client it fetches through.
    """

    factory: Callable[..., object] | None
    qualifier: str | None

    def __init__(self) -> None:
        self.factory = None
        self.qualifier = None
        self.by_qualifier: dict[str | None, Callable[..., object]] = {}

    def set(self, factory: object, *, qualifier: str | None = None) -> _Recorder:
        self.factory = cast("Callable[..., object]", factory)
        self.qualifier = qualifier
        self.by_qualifier[qualifier] = self.factory
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
    handler: object = recorder.factory(http_client=recorder.by_qualifier["api_oidc#http_client"]())

    from xtr_security_http.access_token.oidc import OidcTokenHandler

    assert isinstance(handler, OidcTokenHandler)


def test_a_static_key_set_registers_no_http_client() -> None:
    recorder = _Recorder()

    _ = OidcTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oidc",
        OidcTokenHandlerConfig(
            issuers=("https://issuer.example",),
            audience="shop-api",
            keyset=_jwks(_key()),
        ),
    )

    assert list(recorder.by_qualifier) == ["api_oidc"]


def test_the_handler_is_registered_under_a_name_of_its_own() -> None:
    recorder = _Recorder()

    # The recorder and the absent builder stand in for the container's, of
    # which the factory reads nothing more than what they answer.
    _ = OidcTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oidc",
        _discovery_config(),
    )

    registered = recorder.by_qualifier["api_oidc"]
    assert isinstance(registered, FunctionType)
    assert registered.__name__ == "oidc_token_handler_api_oidc"


def test_the_discovery_fetches_through_the_injected_http_client() -> None:
    from xtr_security_http.access_token.oidc import DiscoveryOidcKeySetProvider

    sink: list[_AsyncCloseable] = []
    recorder = _Recorder()
    _ = (
        OidcTokenHandlerFactory()
        .with_closeables(sink)
        .create(
            recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api_oidc",
            _discovery_config(),
        )
    )
    http_client = object()
    assert recorder.factory is not None

    _ = recorder.factory(http_client=http_client)

    provider = cast("DiscoveryOidcKeySetProvider", sink[0])
    assert provider._http_client is http_client


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
    http_client = recorder.by_qualifier.get(f"{service_id}#http_client")
    _ = recorder.factory() if http_client is None else recorder.factory(http_client=http_client())


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
    from xtr_http_client import HttpxHttpClient

    from xtr_security.access_token.oidc_token_handler_factory import (
        _DISCOVERY_MAX_CONNECTIONS,
        _DISCOVERY_TIMEOUT,
    )

    recorder = _Recorder()
    _ = OidcTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oidc",
        _discovery_config(),
    )

    client = recorder.by_qualifier["api_oidc#http_client"]()
    assert isinstance(client, HttpxHttpClient)

    assert client._default_options["timeout"] == _DISCOVERY_TIMEOUT
    assert client._clients._max_connections == _DISCOVERY_MAX_CONNECTIONS
