"""The userinfo token-handler factory builds a handler that reads the endpoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_cache import ArrayAdapter
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse

from xtr_security.bundle import (
    OidcUserInfoTokenHandlerConfig,
    OidcUserInfoTokenHandlerFactory,
    TokenHandlerFactoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceKey


def _userinfo(members: dict[str, object]) -> MockResponse:
    """A JSON userinfo answer carrying ``members``."""
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
    factory = OidcUserInfoTokenHandlerFactory()

    assert TokenHandlerFactoryInterface in type(factory).__mro__
    assert factory.key == "oidc_user_info"
    assert factory.config_type is OidcUserInfoTokenHandlerConfig


@pytest.mark.anyio
async def test_it_builds_a_handler_that_reads_the_userinfo_endpoint() -> None:
    config = OidcUserInfoTokenHandlerConfig(userinfo_base_uri="https://as.example/userinfo")
    recorder = _Recorder()

    _ = OidcUserInfoTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_userinfo",
        config,
    )
    assert recorder.factory is not None
    client = MockHttpClient(
        _userinfo({"sub": "alice"}),
        base_uri="https://as.example/userinfo",
    )
    build = recorder.factory
    assert build is not None
    handler = build(client=client)

    from xtr_security_http.access_token.oidc import OidcUserInfoTokenHandler

    assert isinstance(handler, OidcUserInfoTokenHandler)
    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_configured_discovery_cache_enables_the_discovery_read() -> None:
    """With a cache configured, the handler reads its endpoint off the issuer's document."""
    config = OidcUserInfoTokenHandlerConfig(
        userinfo_base_uri="https://as.example",
        discovery_cache=ArrayAdapter,
        discovery_cache_key="openid",
    )
    recorder = _Recorder()
    _ = OidcUserInfoTokenHandlerFactory().create(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api_userinfo",
        config,
    )
    document = json.dumps({"userinfo_endpoint": "/userinfo"}).encode()
    answers = iter(
        [
            MockResponse(
                document,
                {
                    "http_code": 200,
                    "response_headers": {"Content-Type": "application/json"},
                    "url": "https://as.example/.well-known/openid-configuration",
                },
            ),
            _userinfo({"sub": "alice"}),
        ],
    )

    def answer(method: str, url: str, _options: object) -> MockResponse:
        del method, url
        return next(answers)

    client = MockHttpClient(answer, base_uri="https://as.example")
    from xtr_security_http.access_token.oidc import OidcUserInfoTokenHandler

    build = recorder.factory
    assert build is not None
    handler = build(client=client, cache=ArrayAdapter())
    assert isinstance(handler, OidcUserInfoTokenHandler)

    badge = await handler.get_user_badge_from("s3cret")
    assert badge.get_user_identifier() == "alice"
