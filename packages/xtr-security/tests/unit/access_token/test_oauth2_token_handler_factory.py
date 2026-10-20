"""The OAuth2 token-handler factory builds a handler that introspects a token."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse

from xtr_security.bundle import (
    Oauth2TokenHandlerConfig,
    Oauth2TokenHandlerFactory,
    TokenHandlerFactoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceKey


def _introspection(members: dict[str, object]) -> MockResponse:
    """A plain JSON introspection response carrying ``members``."""
    return MockResponse(
        json.dumps(members).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@final
class _Recorder:
    """A stand-in service configurator recording the registered factory."""

    factory: Callable[..., object] | None
    qualifier: str | None

    def __init__(self) -> None:
        self.factory = None
        self.qualifier = None

    def set(self, factory: object, *, qualifier: str | None = None) -> _Recorder:
        self.factory = cast("Callable[..., object]", factory)
        self.qualifier = qualifier
        return self

    @property
    def key(self) -> ServiceKey:
        return cast("ServiceKey", (object, self.qualifier))


def test_it_carries_its_interface_key_and_config() -> None:
    factory = Oauth2TokenHandlerFactory()

    assert TokenHandlerFactoryInterface in type(factory).__mro__
    assert factory.key == "oauth2"
    assert factory.config_type is Oauth2TokenHandlerConfig


@pytest.mark.anyio
async def test_it_builds_a_handler_that_introspects_a_token() -> None:
    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        credentials=("shop", "secret"),
        audiences=("shop-api",),
        issuer="https://as.example",
    )
    recorder = _Recorder()

    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    assert recorder.factory is not None
    client = MockHttpClient(
        _introspection(
            {
                "active": True,
                "sub": "alice",
                "iss": "https://as.example",
                "aud": "shop-api",
                "iat": 0,
                "exp": 9_999_999_999,
            },
        ),
        base_uri="https://as.example/introspect",
    )
    build = recorder.factory
    assert build is not None
    handler = build(client=client)

    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    assert isinstance(handler, Oauth2TokenHandler)
    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_it_scopes_the_application_client_with_the_endpoint_and_credentials() -> None:
    """The handler reaches the endpoint through a client scoped here, not the bare one."""
    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        credentials="shop:secret",
    )
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    requests: list[tuple[str, str]] = []

    def answer(method: str, url: str, _options: object) -> MockResponse:
        requests.append((method, url))
        return _introspection({"active": True, "sub": "alice"})

    client = MockHttpClient(answer, base_uri="https://as.example/introspect")
    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    build = recorder.factory
    assert build is not None
    handler = build(client=client)
    assert isinstance(handler, Oauth2TokenHandler)
    _ = await handler.get_user_badge_from("s3cret")

    assert requests == [("POST", "https://as.example/introspect")]


@pytest.mark.anyio
async def test_a_configured_cache_keeps_the_introspection_responses() -> None:
    """A cached handler introspects once; the second badge reads the pool."""
    from xtr_cache import ArrayAdapter

    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        cache=ArrayAdapter,
    )
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    answers = iter(
        [
            _introspection({"active": True, "sub": "alice", "exp": 9_999_999_999}),
            _introspection({"active": True, "sub": "bob"}),
        ],
    )

    def answer(method: str, url: str, _options: object) -> MockResponse:
        del method, url
        return next(answers)

    client = MockHttpClient(answer, base_uri="https://as.example/introspect")
    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    build = recorder.factory
    assert build is not None
    handler = build(client=client, cache=ArrayAdapter())
    assert isinstance(handler, Oauth2TokenHandler)

    first = await handler.get_user_badge_from("s3cret")
    second = await handler.get_user_badge_from("s3cret")

    assert first.get_user_identifier() == second.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_pinned_keyset_verifies_a_signed_response() -> None:
    """A configured signed response is verified against the pinned key set."""
    import json as _json

    from joserfc import jwt as joserfc_jwt
    from joserfc.jwk import KeySet, RSAKey

    key = RSAKey.generate_key(2048, parameters={"kid": "k1"})
    keyset = _json.dumps(KeySet([key]).as_dict(private=False))
    token = joserfc_jwt.encode(
        {"alg": "RS256", "kid": "k1", "typ": "token-introspection+jwt"},
        {
            "iss": "https://as.example",
            "aud": "shop-api",
            "iat": 0,
            "token_introspection": {
                "active": True,
                "sub": "alice",
                "iss": "https://as.example",
                "aud": "shop-api",
                "iat": 0,
                "exp": 9_999_999_999,
            },
        },
        key,
    )
    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        issuer="https://as.example",
        audiences=("shop-api",),
        signed_response_algorithms=("RS256",),
        signed_response_keyset=keyset,
    )
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    client = MockHttpClient(
        MockResponse(
            token.encode(),
            {
                "http_code": 200,
                "response_headers": {"Content-Type": "application/token-introspection+jwt"},
            },
        ),
        base_uri="https://as.example/introspect",
    )
    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    build = recorder.factory
    assert build is not None
    handler = build(client=client)
    assert isinstance(handler, Oauth2TokenHandler)

    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_client_service_is_used_as_it_was_registered() -> None:
    """A named client service carries its own endpoint and credentials."""

    class _Client:
        """A stand-in client service class, already scoped where it is registered."""

    config = Oauth2TokenHandlerConfig(client=_Client)
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    build = recorder.factory
    assert build is not None
    assert build.__annotations__["client"] is _Client

    client = MockHttpClient(
        _introspection({"active": True, "sub": "alice", "iss": "https://as.example"}),
        base_uri="https://as.example/introspect",
    )
    handler = build(client=client)

    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    assert isinstance(handler, Oauth2TokenHandler)
    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_signed_responses_without_a_pinned_keyset_wait_on_discovery() -> None:
    """Algorithms without a key set build; the keys are read at use time."""
    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        signed_response_algorithms=("RS256",),
    )
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    build = recorder.factory
    assert build is not None

    client = MockHttpClient(
        _introspection({"active": True, "sub": "alice", "iss": "https://as.example"}),
        base_uri="https://as.example/introspect",
    )
    handler = build(client=client)

    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    assert isinstance(handler, Oauth2TokenHandler)


@pytest.mark.anyio
async def test_a_discovery_cache_reads_the_verifying_keys_from_the_metadata() -> None:
    """The handler built with a discovery cache accepts a plain response beside a signed one."""
    from xtr_cache import ArrayAdapter

    config = Oauth2TokenHandlerConfig(
        introspection_base_uri="https://as.example/introspect",
        issuer="https://as.example",
        signed_response_algorithms=("RS256",),
        signed_response_enforce=False,
        signed_response_discovery_cache=ArrayAdapter,
        signed_response_discovery_cache_key="metadata",
    )
    recorder = _Recorder()
    _ = Oauth2TokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_oauth2",
        config,
    )
    build = recorder.factory
    assert build is not None
    assert build.__annotations__["discovery_cache"] is ArrayAdapter

    client = MockHttpClient(
        _introspection({"active": True, "sub": "alice", "iss": "https://as.example"}),
        base_uri="https://as.example/introspect",
    )
    handler = build(client=client, discovery_cache=ArrayAdapter())

    from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler

    assert isinstance(handler, Oauth2TokenHandler)
    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"
