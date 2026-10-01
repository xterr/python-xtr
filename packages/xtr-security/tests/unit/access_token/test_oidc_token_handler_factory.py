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
