"""The discovery reader fetches, caches and weighs a provider's document."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar, cast, final

import pytest
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import AuthenticationError, BadMethodCallError

from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_cache_contracts import CacheInterface, Callback, ItemInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface, RequestOptions

_T = TypeVar("_T")

_ISSUER = "https://issuer.example"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


def _json_response(
    body: object,
    headers: Mapping[str, str] | None = None,
    *,
    status: int = 200,
) -> MockResponse:
    """A JSON answer carrying ``body``."""
    return MockResponse(
        json.dumps(body).encode(),
        {
            "http_code": status,
            "response_headers": {"Content-Type": "application/json", **(headers or {})},
        },
    )


def _document(**members: object) -> dict[str, object]:
    """A discovery document for the test issuer, plus ``members``."""
    return {"issuer": _ISSUER, **members}


@final
class _RecordingCache:
    """An array cache that counts every key it was asked for."""

    def __init__(self) -> None:
        self._inner = ArrayAdapter(clock=MockClock(_FROZEN))
        self.keys: list[str] = []

    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: object = None,
    ) -> _T:
        """Compute or answer, recording the key either way."""
        self.keys.append(key)
        return await self._inner.get(key, callback, beta=beta, metadata=metadata)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    async def delete(self, key: str, /) -> bool:
        """Remove the value under ``key``, as the inner cache does."""
        return await self._inner.delete(key)


def _client(
    *answers: MockResponse | Callable[[str, str, RequestOptions], MockResponse],
) -> MockHttpClient:
    """A client answering from ``answers``, in order, at the issuer's base URI."""
    return MockHttpClient(
        list(answers) if answers else _json_response(_document()), base_uri=_ISSUER
    )


def _discovery(  # noqa: PLR0913 -- a test builder over the reader's every knob
    client: HttpClientInterface,
    cache: CacheInterface | None = None,
    *,
    issuer: str | None = None,
    cache_key: str | None = None,
    cache_ttl: int | None = 3600,
    checked_endpoints: Sequence[str] = (),
    checked_mtls_aliases: Sequence[str] = (),
) -> OidcDiscovery:
    """A discovery reader over ``client``, its issuer the test issuer."""
    return OidcDiscovery(
        client,
        cache if cache is not None else _RecordingCache(),
        issuer=issuer,
        cache_key=cache_key,
        cache_ttl=cache_ttl,
        checked_endpoints=checked_endpoints,
        checked_mtls_aliases=checked_mtls_aliases,
    )


@pytest.mark.anyio
async def test_the_document_is_read_from_the_well_known_path_of_the_issuer() -> None:
    requests: list[tuple[str, str, RequestOptions]] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        requests.append((method, url, options))
        return _json_response(_document())

    discovery = _discovery(MockHttpClient(answer, base_uri=_ISSUER), issuer=_ISSUER)

    _ = await discovery.get_configuration()

    assert requests[0][0] == "GET"
    assert requests[0][1] == _DOCUMENT_URI
    assert requests[0][2].get("max_redirects") == 0


@pytest.mark.anyio
async def test_a_relative_url_is_resolved_against_the_client_base_uri() -> None:
    requests: list[str] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        del method, options
        requests.append(url)
        return _json_response(_document())

    discovery = _discovery(MockHttpClient(answer, base_uri=_ISSUER))

    _ = await discovery.get_configuration()

    assert requests == [_DOCUMENT_URI]


@pytest.mark.anyio
async def test_an_absolute_url_is_taken_as_it_stands() -> None:
    requests: list[str] = []

    def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
        del method, options
        requests.append(url)
        return _json_response(_document())

    discovery = OidcDiscovery(
        MockHttpClient(answer),
        _RecordingCache(),
        "https://other.example/openid-configuration",
    )

    _ = await discovery.get_configuration()

    assert requests == ["https://other.example/openid-configuration"]


@pytest.mark.anyio
async def test_an_http_issuer_is_refused() -> None:
    discovery = OidcDiscovery(
        _client(),
        _RecordingCache(),
        issuer="http://issuer.example",
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "must use HTTPS" in str(raised.value)


@pytest.mark.anyio
async def test_a_loopback_issuer_is_allowed_plain_http() -> None:
    discovery = OidcDiscovery(
        MockHttpClient(
            [_json_response({"issuer": "http://localhost:8000"})], base_uri="http://localhost:8000"
        ),
        _RecordingCache(),
        issuer="http://localhost:8000",
    )

    _ = await discovery.get_configuration()


@pytest.mark.anyio
async def test_a_document_announcing_another_issuer_is_refused() -> None:
    discovery = _discovery(
        _client(_json_response({"issuer": "https://evil.example"})), issuer=_ISSUER
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "does not match the configured issuer" in str(raised.value)


@pytest.mark.anyio
async def test_a_trailing_slash_on_either_issuer_is_ignored() -> None:
    discovery = _discovery(
        _client(_json_response({"issuer": f"{_ISSUER}/"})),
        issuer=f"{_ISSUER}/",
    )

    _ = await discovery.get_configuration()


@pytest.mark.anyio
async def test_the_document_is_cached_under_the_given_key() -> None:
    cache = _RecordingCache()
    discovery = _discovery(
        _client(_json_response(_document())), cache, cache_key="oidc", issuer=_ISSUER
    )

    _ = await discovery.get_configuration()

    assert cache.keys == ["oidc"]


@pytest.mark.anyio
async def test_the_cache_key_is_derived_from_the_url_when_none_is_given() -> None:
    cache = _RecordingCache()
    discovery = _discovery(_client(_json_response(_document())), cache, issuer=_ISSUER)

    _ = await discovery.get_configuration()

    assert len(cache.keys) == 1
    assert cache.keys[0].startswith("oidc_discovery.")


@pytest.mark.anyio
async def test_a_warm_entry_answers_without_a_request() -> None:
    client = _client(_json_response(_document()))
    discovery = _discovery(client, issuer=_ISSUER)

    first = await discovery.get_configuration()
    second = await discovery.get_configuration()

    assert first == second
    assert client.get_requests_count() == 1


@pytest.mark.anyio
async def test_the_ttl_is_set_on_the_cache_item() -> None:
    cache = _FakeCache()
    discovery = _discovery(_client(_json_response(_document())), cache, cache_ttl=1234)

    _ = await discovery.get_configuration()

    assert cache.item.ttls == [1234]


@pytest.mark.anyio
async def test_no_ttl_leaves_the_lifetime_to_the_pool() -> None:
    cache = _FakeCache()
    discovery = _discovery(_client(_json_response(_document())), cache, cache_ttl=None)

    _ = await discovery.get_configuration()

    assert cache.item.ttls == []


@final
class _FakeItem:
    """A cache item that records the lifetimes it is given."""

    ttls: list[float | None]

    def __init__(self) -> None:
        self.ttls = []

    def expires_after(self, ttl: float | None) -> _FakeItem:
        """Record the lifetime, chaining as the contract does."""
        self.ttls.append(ttl)
        return self


@final
class _FakeCache:
    """A cache that hands every callback the same recording item."""

    item: _FakeItem
    saved: object

    def __init__(self) -> None:
        self.item = _FakeItem()
        self.saved = None

    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: object = None,
    ) -> _T:
        """Compute the value through the recording item."""
        del key, beta, metadata
        self.saved = await callback(cast("ItemInterface", cast("object", self.item)))
        return cast("_T", cast("object", self.saved))

    async def delete(self, key: str, /) -> bool:
        """Remove nothing; this cache holds one entry."""
        del key
        return True


@pytest.mark.anyio
async def test_the_document_is_memoized_per_instance() -> None:
    cache = _RecordingCache()
    discovery = _discovery(_client(_json_response(_document())), cache, issuer=_ISSUER)

    _ = await discovery.get_configuration()
    _ = await discovery.get_configuration()

    assert cache.keys == [_cache_key_of(discovery)]


@pytest.mark.anyio
async def test_reset_forgets_the_memoized_document() -> None:
    cache = _RecordingCache()
    discovery = _discovery(_client(_json_response(_document())), cache, issuer=_ISSUER)

    _ = await discovery.get_configuration()
    discovery.reset()
    _ = await discovery.get_configuration()

    assert cache.keys == [_cache_key_of(discovery)] * 2


def _cache_key_of(discovery: OidcDiscovery) -> str:
    """The key the discovery reader derives, read back for the assertions above."""
    return discovery._cache_key_value()


@pytest.mark.anyio
async def test_a_checked_endpoint_missing_from_the_document_is_refused() -> None:
    discovery = _discovery(
        _client(_json_response({"issuer": _ISSUER})),
        issuer=_ISSUER,
        checked_endpoints=("userinfo_endpoint",),
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert (
        str(raised.value) == 'The "userinfo_endpoint" is missing from the OIDC discovery document.'
    )


@pytest.mark.anyio
async def test_an_http_checked_endpoint_of_an_https_document_is_refused() -> None:
    discovery = _discovery(
        _client(_json_response(_document(userinfo_endpoint="http://issuer.example/userinfo"))),
        issuer=_ISSUER,
        checked_endpoints=("userinfo_endpoint",),
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert str(raised.value) == (
        'The "userinfo_endpoint" found in the OIDC discovery document must use the '
        '"https" scheme, "http" given.'
    )


@pytest.mark.anyio
async def test_an_http_checked_endpoint_of_an_http_document_is_allowed() -> None:
    discovery = OidcDiscovery(
        MockHttpClient(
            [
                _json_response(
                    {
                        "issuer": "http://localhost:8000",
                        "userinfo_endpoint": "http://localhost:8000/userinfo",
                    }
                )
            ],
            base_uri="http://localhost:8000",
        ),
        _RecordingCache(),
        issuer="http://localhost:8000",
        checked_endpoints=("userinfo_endpoint",),
    )

    _ = await discovery.get_configuration()


@pytest.mark.anyio
async def test_a_checked_mtls_alias_is_weighed_like_an_endpoint() -> None:
    discovery = _discovery(
        _client(
            _json_response(
                _document(
                    mtls_endpoint_aliases={"token_endpoint": "http://issuer.example/token"},
                ),
            ),
        ),
        issuer=_ISSUER,
        checked_mtls_aliases=("token_endpoint",),
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert str(raised.value) == (
        'The "mtls_endpoint_aliases.token_endpoint" found in the OIDC discovery '
        'document must use the "https" scheme, "http" given.'
    )


@pytest.mark.anyio
async def test_an_absent_mtls_alias_is_skipped() -> None:
    discovery = _discovery(
        _client(_json_response(_document())),
        issuer=_ISSUER,
        checked_mtls_aliases=("token_endpoint",),
    )

    _ = await discovery.get_configuration()


@pytest.mark.anyio
async def test_an_oversized_document_is_refused() -> None:
    discovery = _discovery(_client(_json_response({"padding": "x" * (1024 * 1024 + 1)})))

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert str(raised.value) == "The OIDC discovery document exceeds the maximum size of 1 MiB."


@pytest.mark.anyio
async def test_a_document_that_is_not_json_is_refused() -> None:
    discovery = _discovery(MockHttpClient([MockResponse(b"not json")], base_uri=_ISSUER))

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "could not be decoded" in str(raised.value)


@pytest.mark.anyio
async def test_a_document_that_is_not_a_json_object_is_refused() -> None:
    discovery = _discovery(_client(_json_response(["not", "an", "object"])))

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "not a JSON object" in str(raised.value)


@pytest.mark.anyio
async def test_an_unreachable_document_is_refused() -> None:
    discovery = _discovery(
        MockHttpClient([MockResponse(b"", {"error": "no answer"})], base_uri=_ISSUER)
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "could not be fetched" in str(raised.value)


@pytest.mark.anyio
async def test_get_secure_endpoint_returns_the_announced_https_endpoint() -> None:
    discovery = _discovery(
        _client(_json_response(_document(userinfo_endpoint=f"{_ISSUER}/userinfo"))),
        issuer=_ISSUER,
    )

    assert await discovery.get_secure_endpoint("userinfo_endpoint") == f"{_ISSUER}/userinfo"


@pytest.mark.anyio
async def test_get_secure_endpoint_refuses_a_missing_endpoint() -> None:
    discovery = _discovery(_client(_json_response(_document())), issuer=_ISSUER)

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_secure_endpoint("userinfo_endpoint")

    assert str(raised.value) == 'The OIDC provider does not announce any "userinfo_endpoint".'


@pytest.mark.anyio
async def test_get_secure_endpoint_refuses_a_plain_http_endpoint() -> None:
    discovery = _discovery(
        _client(_json_response(_document(userinfo_endpoint="http://issuer.example/userinfo"))),
        issuer=_ISSUER,
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_secure_endpoint("userinfo_endpoint")

    assert "must use HTTPS" in str(raised.value)


@pytest.mark.anyio
async def test_get_issuer_returns_the_announced_issuer() -> None:
    discovery = _discovery(_client(_json_response(_document())), issuer=_ISSUER)

    assert await discovery.get_issuer() == _ISSUER


@pytest.mark.anyio
async def test_get_issuer_refuses_a_document_announcing_none() -> None:
    cache = _RecordingCache()

    async def announce_no_issuer(item: ItemInterface) -> dict[str, object]:
        """A warm entry another writer left, announcing no issuer."""
        del item
        return {"url": _DOCUMENT_URI, "payload": json.dumps({"token_endpoint": f"{_ISSUER}/token"})}

    _ = await cache.get("oidc", announce_no_issuer)
    discovery = _discovery(_client(), cache, cache_key="oidc", issuer=_ISSUER)

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_issuer()

    assert str(raised.value) == 'The OIDC provider does not announce any "issuer".'


@pytest.mark.anyio
async def test_get_issuer_refuses_a_reader_with_no_expected_issuer() -> None:
    discovery = _discovery(_client(_json_response(_document())))

    with pytest.raises(BadMethodCallError):
        _ = await discovery.get_issuer()


@pytest.mark.anyio
async def test_prefetch_sends_the_request_and_get_configuration_consumes_it() -> None:
    client = _client(_json_response(_document()))
    discovery = _discovery(client, issuer=_ISSUER)

    await discovery.prefetch()
    assert client.get_requests_count() == 1

    _ = await discovery.get_configuration()
    assert client.get_requests_count() == 1


@pytest.mark.anyio
async def test_prefetch_twice_sends_one_request() -> None:
    client = _client(_json_response(_document()))
    discovery = _discovery(client, issuer=_ISSUER)

    await discovery.prefetch()
    await discovery.prefetch()

    assert client.get_requests_count() == 1


@pytest.mark.anyio
async def test_prefetch_after_a_read_sends_nothing() -> None:
    client = _client(_json_response(_document()))
    discovery = _discovery(client, issuer=_ISSUER)

    _ = await discovery.get_configuration()
    await discovery.prefetch()

    assert client.get_requests_count() == 1


@pytest.mark.anyio
async def test_a_prefetched_request_is_dropped_when_the_cache_was_warmed_elsewhere() -> None:
    cache = _RecordingCache()
    first = _discovery(_client(_json_response(_document())), cache, issuer=_ISSUER)
    _ = await first.get_configuration()

    second = _discovery(_client(_json_response(_document())), cache, issuer=_ISSUER)
    await second.prefetch()
    _ = await second.get_configuration()

    # The warm entry answers both reads; the prefetched response is dropped
    # unread rather than consumed by the second one.
    assert cache.keys == [_cache_key_of(first)] * 2


@pytest.mark.anyio
async def test_a_response_that_fails_to_read_is_refused() -> None:
    discovery = _discovery(cast("HttpClientInterface", cast("object", _FailingClient())))

    with pytest.raises(AuthenticationError) as raised:
        _ = await discovery.get_configuration()

    assert "could not be fetched" in str(raised.value)


@final
class _FailingClient:
    """A client whose every response fails to read its body."""

    async def request(self, method: str, url: str, **options: object) -> HttpResponseInterface:
        """Answer with the unreadable response."""
        del method, url, options
        return cast("HttpResponseInterface", cast("object", _UnreadableResponse()))


@final
class _UnreadableResponse:
    """A response whose body cannot be read off the transfer."""

    def get_info(self, key: str | None = None) -> object:
        """Name the URL the transfer was made to."""
        del key
        return _DOCUMENT_URI

    def get_header(self, name: str) -> list[str]:
        """Carry no headers."""
        del name
        return []

    async def get_content(self, throw: bool = True) -> bytes:
        """Fail, as a transfer that broke mid-body does."""
        del throw
        raise RuntimeError("the transfer broke")

    async def cancel(self) -> None:
        """Abandon nothing; the transfer already failed."""

    async def __aenter__(self) -> _UnreadableResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close nothing; the transfer already failed."""


def test_is_secure_url_accepts_https() -> None:
    assert OidcDiscovery.is_secure_url("https://issuer.example")
    assert OidcDiscovery.is_secure_url("HTTPS://issuer.example")


def test_is_secure_url_refuses_plain_http() -> None:
    assert not OidcDiscovery.is_secure_url("http://issuer.example")


def test_is_secure_url_accepts_the_loopback_hosts() -> None:
    assert OidcDiscovery.is_secure_url("http://localhost:8000")
    assert OidcDiscovery.is_secure_url("http://127.0.0.1:8000")
    assert OidcDiscovery.is_secure_url("http://[::1]:8000")


def test_is_secure_url_accepts_dotted_localhost() -> None:
    assert OidcDiscovery.is_secure_url("http://app.localhost:8000")
    assert not OidcDiscovery.is_secure_url("http://localhost.example:8000")
