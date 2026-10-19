"""The rebuilt discovery key-set provider fetches and caches through the contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from joserfc.jwk import KeySet, RSAKey
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.access_token.oidc.exception.oidc_key_set_error import OidcKeySetError
from xtr_security_http.oidc.discovery_oidc_key_set_provider import DiscoveryOidcKeySetProvider

if TYPE_CHECKING:
    from xtr_cache_contracts import CacheInterface, ItemInterface

_ISSUER = "https://issuer.example"
_JWKS_URI = "https://issuer.example/jwks.json"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_NOW = 1_000_000


def _key(kid: str = "k1") -> RSAKey:
    """Generate an RSA key carrying ``kid``."""
    return RSAKey.generate_key(2048, parameters={"kid": kid, "use": "sig"})


def _jwks_response(*keys: RSAKey, cache_control: str | None = None) -> MockResponse:
    """A JWKS answer for ``keys``, optionally advertising its freshness."""
    headers = {"Content-Type": "application/json"}
    if cache_control is not None:
        headers["Cache-Control"] = cache_control
    return MockResponse(
        json.dumps(KeySet(list(keys)).as_dict(private=False)).encode(),
        {"http_code": 200, "response_headers": headers},
    )


def _document_response(**members: object) -> MockResponse:
    """A discovery document for the test issuer, plus ``members``."""
    body: dict[str, object] = {"issuer": _ISSUER, "jwks_uri": _JWKS_URI, **members}
    return MockResponse(
        json.dumps(body).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@final
class _Server:
    """A scripted issuer: a discovery document and a JWKS, both in memory."""

    def __init__(self, key: RSAKey) -> None:
        self.key = key
        self.discovery_requests = 0
        self.jwks_requests = 0

    def client(self) -> MockHttpClient:
        """A client answering this issuer's two paths."""
        server = self

        def answer(method: str, url: str, options: object) -> MockResponse:
            del method, options
            if url == _DOCUMENT_URI:
                server.discovery_requests += 1
                return _document_response()
            if url == _JWKS_URI:
                server.jwks_requests += 1
                return _jwks_response(server.key)
            return MockResponse(b"{}", {"http_code": 404})

        return MockHttpClient(answer, base_uri=_ISSUER)


def _provider(
    client: MockHttpClient,
    cache: CacheInterface,
    **kwargs: object,
) -> DiscoveryOidcKeySetProvider:
    """A provider over ``client`` and ``cache``, its base URI the test issuer."""
    return DiscoveryOidcKeySetProvider(client, cache, base_uri=_ISSUER, **kwargs)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


@pytest.mark.anyio
async def test_it_discovers_the_jwks_uri_from_the_base_uri() -> None:
    key = _key()
    server = _Server(key)
    provider = _provider(server.client(), ArrayAdapter())

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]
    assert server.discovery_requests == 1
    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_it_fetches_a_given_jwks_uri_without_discovery() -> None:
    key = _key()
    server = _Server(key)
    provider = DiscoveryOidcKeySetProvider(
        server.client(),
        ArrayAdapter(),
        jwks_uri=_JWKS_URI,
    )

    _ = await provider.get_key_set()

    assert server.discovery_requests == 0
    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_document_announcing_another_issuer_is_refused() -> None:
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps({"issuer": "https://evil.example", "jwks_uri": _JWKS_URI}).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    provider = _provider(client, ArrayAdapter())

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_cached_set_answers_without_a_fetch() -> None:
    key = _key()
    server = _Server(key)
    provider = _provider(server.client(), ArrayAdapter())

    _ = await provider.get_key_set()
    _ = await provider.get_key_set()

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_the_set_is_refetched_once_the_advertised_ttl_lapses() -> None:
    key = _key()
    server = _Server(key)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    provider = _provider(
        server.client(),
        ArrayAdapter(clock=clock),
        clock=clock,
    )

    _ = await provider.get_key_set()
    clock.sleep(3700)
    _ = await provider.get_key_set()

    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_the_advertised_max_age_wins_over_the_default_ttl() -> None:
    key = _key()
    answers: list[MockResponse] = [
        _document_response(),
        _jwks_response(key, cache_control="max-age=60"),
        _jwks_response(key, cache_control="max-age=60"),
    ]
    client = MockHttpClient(answers, base_uri=_ISSUER)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    provider = _provider(client, ArrayAdapter(clock=clock), clock=clock)

    _ = await provider.get_key_set()
    clock.sleep(61)
    _ = await provider.get_key_set()

    assert client.get_requests_count() == 3


@pytest.mark.anyio
async def test_a_forced_refresh_within_the_cooldown_serves_the_cached_set() -> None:
    key = _key()
    server = _Server(key)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    provider = _provider(server.client(), ArrayAdapter(clock=clock), clock=clock)

    _ = await provider.get_key_set()
    clock.sleep(30)
    _ = await provider.get_key_set(force_refresh=True)

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_forced_refresh_past_the_cooldown_refetches() -> None:
    key = _key()
    server = _Server(key)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    provider = _provider(server.client(), ArrayAdapter(clock=clock), clock=clock)

    _ = await provider.get_key_set()
    clock.sleep(61)
    _ = await provider.get_key_set(force_refresh=True)

    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_a_warm_entry_without_a_fetch_stamp_is_refetched_on_force() -> None:
    key = _key()
    server = _Server(key)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    cache = ArrayAdapter(default_lifetime=3600, clock=clock)

    async def written_elsewhere(item: ItemInterface) -> dict[str, object]:
        """A warm entry another writer left, carrying no fetch stamp."""
        del item
        return {"keys": [dict(key.as_dict(private=False))]}

    provider = DiscoveryOidcKeySetProvider(
        server.client(),
        cache,
        jwks_uri=_JWKS_URI,
        clock=clock,
    )
    _ = await cache.get(provider._cache_key(_JWKS_URI), written_elsewhere)

    _ = await provider.get_key_set(force_refresh=True)

    # No stamp says when the entry was fetched, so a forced refresh refetches.
    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_forced_refresh_with_a_base_uri_refetches_but_not_the_document() -> None:
    key = _key()
    server = _Server(key)
    clock = MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    provider = _provider(server.client(), ArrayAdapter(clock=clock), clock=clock)

    _ = await provider.get_key_set()
    clock.sleep(61)
    _ = await provider.get_key_set(force_refresh=True)

    # The discovery document is the cache's, not the provider's own: a forced
    # refresh refetches the keys, and the document answers from the cache.
    assert server.discovery_requests == 1
    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_a_fetch_failure_becomes_a_key_set_error() -> None:
    client = MockHttpClient(
        [MockResponse(b"", {"error": "no answer"})],
        base_uri=_ISSUER,
    )
    provider = DiscoveryOidcKeySetProvider(
        client,
        ArrayAdapter(),
        jwks_uri=f"{_ISSUER}/missing.json",
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_malformed_jwks_document_becomes_a_key_set_error() -> None:
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps({"keys": [{"kty": "nonsense"}]}).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    provider = DiscoveryOidcKeySetProvider(client, ArrayAdapter(), jwks_uri=_JWKS_URI)

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_jwks_answer_that_is_not_an_object_becomes_a_key_set_error() -> None:
    client = MockHttpClient(
        [MockResponse(json.dumps(["not", "an", "object"]).encode(), {"http_code": 200})],
        base_uri=_ISSUER,
    )
    provider = DiscoveryOidcKeySetProvider(client, ArrayAdapter(), jwks_uri=_JWKS_URI)

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_document_without_a_jwks_uri_is_refused() -> None:
    client = MockHttpClient(
        [MockResponse(json.dumps({"issuer": _ISSUER}).encode(), {"http_code": 200})],
        base_uri=_ISSUER,
    )
    provider = _provider(client, ArrayAdapter())

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_an_http_jwks_uri_is_refused() -> None:
    provider = DiscoveryOidcKeySetProvider(
        MockHttpClient([], base_uri=_ISSUER),
        ArrayAdapter(),
        jwks_uri="http://issuer.example/jwks.json",
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_an_http_base_uri_is_refused_by_the_discovery_reader() -> None:
    provider = DiscoveryOidcKeySetProvider(
        MockHttpClient([], base_uri="http://issuer.example"),
        ArrayAdapter(),
        base_uri="http://issuer.example",
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_an_insecure_http_issuer_is_allowed_through_the_dev_door() -> None:
    key = _key()
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps(
                    {
                        "issuer": "http://issuer.example",
                        "jwks_uri": "http://issuer.example/jwks.json",
                    }
                ).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
            _jwks_response(key),
        ],
        base_uri="http://issuer.example",
    )
    provider = DiscoveryOidcKeySetProvider(
        client,
        ArrayAdapter(),
        base_uri="http://issuer.example",
        allow_insecure_http=True,
    )

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_a_dev_door_document_without_a_jwks_uri_is_refused() -> None:
    from hashlib import sha256  # noqa: PLC0415 -- test-local helper

    cache = ArrayAdapter(
        default_lifetime=3600, clock=MockClock(datetime.fromtimestamp(_NOW, tz=UTC))
    )
    # A warm entry another writer left: the discovery reader checks a
    # document it fetches, not one the cache hands back, so the provider's
    # own guard is what refuses it.
    key = f"oidc_discovery.{sha256(b'.well-known/openid-configuration').hexdigest()}"

    async def written_elsewhere(item: ItemInterface) -> dict[str, object]:
        del item
        return {"url": _DOCUMENT_URI, "payload": json.dumps({"issuer": "http://issuer.example"})}

    _ = await cache.get(key, written_elsewhere)
    client = MockHttpClient([], base_uri="http://issuer.example")
    provider = DiscoveryOidcKeySetProvider(
        client,
        cache,
        base_uri="http://issuer.example",
        allow_insecure_http=True,
    )

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


@pytest.mark.anyio
async def test_a_loopback_issuer_needs_no_dev_door() -> None:
    key = _key()
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps(
                    {
                        "issuer": "http://localhost:8000",
                        "jwks_uri": "http://localhost:8000/jwks.json",
                    }
                ).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
            _jwks_response(key),
        ],
        base_uri="http://localhost:8000",
    )
    provider = DiscoveryOidcKeySetProvider(
        client,
        ArrayAdapter(),
        base_uri="http://localhost:8000",
    )

    key_set = await provider.get_key_set()

    assert [held.kid for held in key_set.keys] == [key.kid]


@pytest.mark.anyio
async def test_a_discovered_http_jwks_uri_of_an_https_issuer_is_refused() -> None:
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps(
                    {"issuer": _ISSUER, "jwks_uri": "http://issuer.example/jwks.json"}
                ).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    provider = _provider(client, ArrayAdapter())

    with pytest.raises(OidcKeySetError):
        _ = await provider.get_key_set()


def test_giving_neither_endpoint_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(MockHttpClient(), ArrayAdapter())


def test_giving_both_endpoints_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DiscoveryOidcKeySetProvider(
            MockHttpClient(),
            ArrayAdapter(),
            base_uri=_ISSUER,
            jwks_uri=_JWKS_URI,
        )


@pytest.mark.anyio
async def test_aclose_is_a_no_op() -> None:
    provider = DiscoveryOidcKeySetProvider(
        MockHttpClient([], base_uri=_ISSUER),
        ArrayAdapter(),
        jwks_uri=_JWKS_URI,
    )

    await provider.aclose()
