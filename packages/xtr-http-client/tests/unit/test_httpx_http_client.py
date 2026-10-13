from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anyio
import httpx
import pytest
from xtr_http_message import Request

from xtr_http_client import HttpxHttpClient
from xtr_http_client.exception import InvalidArgumentError, TransportTimeoutError
from xtr_http_client.httpx_http_client import (
    _basic_credentials,
    _hops,
    _reachable,
    _seconds,
)
from xtr_http_client.internal.httpx_clients import _key

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import TypeAlias

    from xtr_http_client_contracts import RequestOptions

    _Handler: TypeAlias = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]

pytestmark = pytest.mark.anyio


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
