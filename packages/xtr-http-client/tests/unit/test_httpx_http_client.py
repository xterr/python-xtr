from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anyio
import anyio.lowlevel
import httpx
import pytest
from xtr_http_message import Request

from xtr_http_client import HttpxHttpClient
from xtr_http_client.exception import (
    InvalidArgumentError,
    TransportError,
    TransportTimeoutError,
)
from xtr_http_client.httpx_http_client import (
    _base_uri,
    _basic_credentials,
    _checked,
    _headers,
    _hops,
    _payload,
    _pinned,
    _reachable,
    _seconds,
    _target,
    _values,
)
from xtr_http_client.internal.httpx_clients import _key

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine, Mapping, Sequence
    from typing import TypeAlias

    from xtr_http_client_contracts import RequestOptions

    _Handler: TypeAlias = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]

pytestmark = pytest.mark.anyio


async def _pieces(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        await anyio.lowlevel.checkpoint()
        yield part


async def _not_bytes() -> AsyncIterator[bytes]:
    await anyio.lowlevel.checkpoint()
    yield cast("bytes", cast("object", ["not", "bytes"]))


def _answering(client: HttpxHttpClient, handler: _Handler) -> None:
    """Put a client answering from ``handler`` in the pool this client would reach for."""
    key = _key(client._default_options)
    client._clients._clients[key] = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    client._clients._resolved[key] = {}


# ── the URL a request is made to ────────────────────────────────────────────


def test_a_host_named_in_another_script_is_rewritten_to_the_form_that_reaches_it() -> None:
    assert _reachable("http://Bücher.example:8057/") == "http://xn--bcher-kva.example:8057/"


def test_an_ascii_url_is_left_exactly_as_it_was_given() -> None:
    assert _reachable("http://foo:b%3Dar@localhost:8057/a?b=c") == (
        "http://foo:b%3Dar@localhost:8057/a?b=c"
    )


def test_a_host_no_name_server_could_hold_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="for "):
        _ = _reachable("http://" + "ü" * 100 + ".example/")


def test_a_relative_uri_is_resolved_against_the_base() -> None:
    url = _target(Request("GET", "../404"), {"base_uri": "http://example.test/abc/"})

    assert str(url) == "http://example.test/404"


def test_the_first_of_several_bases_is_the_one_a_single_attempt_resolves_against() -> None:
    assert _base_uri(["http://first.test/", "http://second.test/"]) == "http://first.test/"


@pytest.mark.parametrize("base", [42, [], {}, [7]])
def test_a_base_that_is_not_a_url_is_refused(base: object) -> None:
    with pytest.raises(InvalidArgumentError, match='Option "base_uri"'):
        _ = _base_uri(base)


def test_the_query_option_is_merged_into_the_one_the_uri_already_carried() -> None:
    url = _target(Request("GET", "http://example.test/?a=a"), {"query": {"b": "b"}})

    assert str(url) == "http://example.test/?a=a&b=b"


def test_an_absolute_uri_ignores_the_base() -> None:
    url = _target(Request("GET", "http://example.test/here"), {"base_uri": "http://other.test/"})

    assert str(url) == "http://example.test/here"


# ── the headers sent ────────────────────────────────────────────────────────


def test_the_host_a_request_worked_out_for_itself_is_not_sent() -> None:
    headers = _headers(Request("GET", "http://example.test:8057/"), {})

    assert headers == []


def test_a_host_set_by_hand_is_sent_as_given() -> None:
    request = Request("GET", "http://example.test/", headers={"Host": "chosen.test"})

    assert _headers(request, {}) == [("Host", "chosen.test")]


def test_a_header_the_request_carries_wins_and_one_it_lacks_is_filled_in() -> None:
    request = Request("GET", "http://example.test/", headers={"Foo": "from-request"})

    headers = _headers(request, {"headers": {"foo": "from-options", "Bar": "from-options"}})

    assert headers == [("Foo", "from-request"), ("Bar", "from-options")]


def test_a_header_given_several_values_sends_all_of_them() -> None:
    headers = _headers(Request("GET", "/"), {"headers": {"Accept": ["text/html", "text/plain"]}})

    assert headers == [("Accept", "text/html"), ("Accept", "text/plain")]


@pytest.mark.parametrize("value", [42, None])
def test_a_header_value_that_is_neither_text_nor_a_list_is_refused(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='Option "headers"'):
        _ = _values("Accept", value)


def test_a_bearer_token_fills_an_authorization_the_request_has_none_of() -> None:
    headers = _headers(Request("GET", "/"), {"auth_bearer": "a-token"})

    assert headers == [("Authorization", "Bearer a-token")]


def test_a_bearer_token_replaces_no_authorization_the_request_carries() -> None:
    request = Request("GET", "/", headers={"Authorization": "Bearer from-the-request"})

    headers = _headers(request, {"auth_bearer": "from-the-option"})

    assert headers == [("Authorization", "Bearer from-the-request")]


# ── the credentials sent ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("basic", "expected"),
    [
        ("user:password", ("user", "password")),
        ("user", ("user", "")),
        (("user", "password"), ("user", "password")),
        (("user",), ("user", "")),
    ],
)
def test_basic_credentials_are_read_in_every_shape_the_contract_allows(
    basic: object,
    expected: tuple[str, str],
) -> None:
    assert _basic_credentials({"auth_basic": basic}, []) == expected


def test_no_credentials_are_sent_where_the_request_already_has_an_authorization() -> None:
    headers = [("Authorization", "Bearer from-the-request")]

    assert _basic_credentials({"auth_basic": "user:password"}, headers) is None


def test_no_credentials_are_sent_where_none_were_asked_for() -> None:
    assert _basic_credentials({}, []) is None


# ── the body sent ───────────────────────────────────────────────────────────


async def test_a_request_body_is_what_is_sent_and_is_labelled_as_a_form() -> None:
    headers: list[tuple[str, str]] = []

    payload = await _payload(Request("POST", "/", body=b"foo=bar"), {}, headers)

    assert payload.content == b"foo=bar"
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


async def test_a_request_body_keeps_the_content_type_the_request_declared() -> None:
    request = Request("POST", "/", headers={"Content-Type": "text/plain"}, body=b"hello")
    headers = _headers(request, {})

    payload = await _payload(request, {}, headers)

    assert payload.content == b"hello"
    assert headers == [("Content-Type", "text/plain")]


@pytest.mark.parametrize("option", [{"body": {"foo": "baz"}}, {"json": {"foo": "baz"}}])
async def test_a_body_given_twice_is_refused_word_for_word(
    option: Mapping[str, object],
) -> None:
    request = Request("POST", "/", body=b"foo=bar")
    expected = (
        'Define either the request body or the "body" or "json" option, '
        "setting both is not supported."
    )

    with pytest.raises(InvalidArgumentError) as refusal:
        _ = await _payload(request, option, [])

    assert str(refusal.value) == expected


async def test_a_json_option_is_sent_as_a_document() -> None:
    payload = await _payload(Request("POST", "/"), {"json": {"foo": "bar"}}, [])

    assert payload.document == {"foo": "bar"}
    assert payload.content is None


async def test_a_mapping_body_is_sent_as_a_form_the_backend_encodes() -> None:
    headers: list[tuple[str, str]] = []

    payload = await _payload(Request("POST", "/"), {"body": {"foo": "bar"}}, headers)

    assert payload.form == {"foo": "bar"}
    assert headers == []


async def test_a_text_body_is_sent_as_it_is() -> None:
    headers: list[tuple[str, str]] = []

    payload = await _payload(Request("POST", "/"), {"body": "foo=bar"}, headers)

    assert payload.content == "foo=bar"
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


async def test_a_body_produced_in_pieces_is_sent_as_it_is_produced() -> None:
    headers: list[tuple[str, str]] = []

    payload = await _payload(Request("POST", "/"), {"body": _pieces(b"foo=bar")}, headers)

    assert payload.content is not None
    assert headers == [("Content-Type", "application/x-www-form-urlencoded")]


@pytest.mark.parametrize("body", [b"", "", 42])
async def test_a_body_with_nothing_in_it_sends_nothing(body: object) -> None:
    payload = await _payload(Request("POST", "/"), {"body": body}, [])

    assert payload == (None, None, None)


async def test_a_body_producing_anything_other_than_bytes_fails_the_request() -> None:
    pieces = _checked(_not_bytes())

    with pytest.raises(TransportError, match="which is not bytes"):
        _ = await anext(pieces)


# ── the address a host is pinned to ─────────────────────────────────────────


def test_a_pinned_host_is_reached_at_its_address_and_still_named_in_the_headers() -> None:
    headers = [("Host", "stale.test")]

    url, extensions = _pinned(
        httpx.URL("http://pinned.example:8057/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        {},
        headers,
    )

    assert str(url) == "http://127.0.0.1:8057/"
    assert headers == [("Host", "pinned.example:8057")]
    assert extensions == {"sni_hostname": "pinned.example"}


def test_a_pinned_host_on_a_standard_port_is_named_without_one() -> None:
    headers: list[tuple[str, str]] = []

    _, _ = _pinned(
        httpx.URL("http://pinned.example/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        {},
        headers,
    )

    assert headers == [("Host", "pinned.example")]


def test_a_host_pinned_once_stays_pinned_for_the_pool() -> None:
    remembered: dict[str, str] = {}

    _ = _pinned(
        httpx.URL("http://pinned.example/"),
        {"resolve": {"pinned.example": "127.0.0.1"}},
        remembered,
        [],
    )
    url, extensions = _pinned(httpx.URL("http://pinned.example/"), {}, remembered, [])

    assert str(url) == "http://127.0.0.1/"
    assert extensions == {"sni_hostname": "pinned.example"}


def test_a_host_nobody_pinned_is_left_to_a_resolver() -> None:
    headers: list[tuple[str, str]] = []

    url, extensions = _pinned(httpx.URL("http://example.test/"), {}, {}, headers)

    assert str(url) == "http://example.test/"
    assert extensions == {}
    assert headers == []


# ── the limits a request is held to ─────────────────────────────────────────


@pytest.mark.parametrize(("given", "expected"), [(0.0, None), (0, None), (1.5, 1.5), ("x", None)])
def test_a_limit_of_zero_is_no_limit(given: object, expected: float | None) -> None:
    assert _seconds(given) == expected


@pytest.mark.parametrize(("given", "expected"), [(20, 20), (0, 0), (-1, 0), ("x", 0)])
def test_fewer_than_no_hops_is_no_hops(given: object, expected: int) -> None:
    assert _hops(given) == expected


# ── the client itself ───────────────────────────────────────────────────────


async def test_a_head_that_outlasts_the_whole_duration_is_a_timeout() -> None:
    async def slowly(request: httpx.Request) -> httpx.Response:
        del request
        await anyio.sleep(1)

        return httpx.Response(200)

    client = HttpxHttpClient()
    _answering(client, slowly)

    with pytest.raises(TransportTimeoutError, match="Maximum duration reached"):
        _ = await client.request("GET", "http://example.test/", max_duration=0.05)

    await client.aclose()


async def test_a_client_closes_its_connections_when_its_block_ends() -> None:
    async with HttpxHttpClient() as client:
        pool, _ = client._clients.for_options(client._default_options)

    assert pool.is_closed


async def test_a_scoped_client_shares_the_connections_of_the_one_it_came_from() -> None:
    client = HttpxHttpClient()
    scoped = client.with_options(base_uri="http://example.test/")

    assert scoped is not client
    assert scoped._clients is client._clients

    await client.aclose()


async def test_a_request_is_refused_before_anything_is_sent_for_an_invalid_method() -> None:
    client = HttpxHttpClient()

    with pytest.raises(InvalidArgumentError, match="only uppercase letters"):
        _ = await client.request("get", "http://example.test/")

    await client.aclose()


async def test_the_default_options_a_client_was_built_with_are_refused_when_unknown() -> None:
    unknown = cast("RequestOptions", cast("object", {"capture_peer_cert": True}))

    with pytest.raises(InvalidArgumentError, match="Unsupported option"):
        _ = HttpxHttpClient(unknown)


async def test_a_request_carries_the_method_and_headers_it_was_given() -> None:
    seen: list[httpx.Request] = []

    async def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)

        return httpx.Response(204)

    client = HttpxHttpClient()
    _answering(client, record)

    response = await client.request("GET", "http://example.test/", headers={"Foo": "baR"})

    assert response.get_status_code() == 204
    assert seen[0].headers["foo"] == "baR"
    assert seen[0].headers["host"] == "example.test"

    await client.aclose()


async def test_an_unknown_option_is_refused_rather_than_quietly_obeyed() -> None:
    client = HttpxHttpClient()
    unknown = cast("RequestOptions", cast("object", {"capture_peer_cert": True}))

    with pytest.raises(InvalidArgumentError, match="Unsupported option"):
        _ = await client.send_request(Request("GET", "http://example.test/"), **unknown)

    await client.aclose()


def test_the_values_of_a_header_sequence_are_each_sent_as_text() -> None:
    assert _values("X-Count", cast("Sequence[object]", [1, 2])) == [
        ("X-Count", "1"),
        ("X-Count", "2"),
    ]
