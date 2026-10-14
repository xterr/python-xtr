"""End-to-end: an application listing HttpClientBundle calls out through what it configured."""

from __future__ import annotations

from typing import cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_http_client_contracts import HttpClientInterface
from xtr_rate_limiter import RateLimiterFactoryInterface

from xtr_http_client import HttpxHttpClient, MockHttpClient, MockResponse, TraceableHttpClient

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_http_client"


def _kernel() -> Kernel:
    return Kernel(APP, env="test")


def _transport_of(client: object) -> object:
    """Return the transport under every layer ``client`` is wrapped in."""
    while (inner := cast("object", getattr(client, "_client", None))) is not None:
        client = inner
    return client


async def test_the_default_client_makes_a_failed_request_again() -> None:
    async with await _kernel().boot() as booted:
        mock = await booted.container.get(MockHttpClient)
        mock.set_response_factory([MockResponse(b"", {"http_code": 500}), MockResponse(b"ok")])
        client = await booted.container.get(HttpClientInterface)

        async with await client.request("GET", "https://example.test/orders") as response:
            assert response.get_status_code() == 200
            assert response.get_info("retry_count") == 1


async def test_the_default_client_writes_down_every_request() -> None:
    async with await _kernel().boot() as booted:
        client = await booted.container.get(HttpClientInterface)

        async with await client.request("GET", "https://example.test/orders"):
            pass

        assert isinstance(client, TraceableHttpClient)
        traced = client.get_traced_requests()
        assert [(trace["method"], trace["url"]) for trace in traced] == [
            ("GET", "https://example.test/orders")
        ]


async def test_a_scoped_client_resolves_a_relative_url_against_its_base_uri() -> None:
    async with await _kernel().boot() as booted:
        client = await booted.container.get(HttpClientInterface, "github")

        async with await client.request("GET", "repos") as response:
            assert response.get_info("url") == "https://api.github.test/repos"


async def test_a_scoped_client_sends_its_own_headers() -> None:
    async with await _kernel().boot() as booted:
        answer = MockResponse()
        (await booted.container.get(MockHttpClient)).set_response_factory(answer)
        client = await booted.container.get(HttpClientInterface, "github")

        async with await client.request("GET", "repos"):
            pass

        assert answer.get_request_options()["headers"] == {"Accept": "application/vnd.github+json"}


async def test_a_paced_client_takes_its_turn_from_its_rate_limiter() -> None:
    async with await _kernel().boot() as booted:
        client = await booted.container.get(HttpClientInterface, "paced")

        async with await client.request("GET", "https://paced.test/orders"):
            pass

        limiters = await booted.container.get(RateLimiterFactoryInterface, "api")
        assert (await limiters.create().consume(0)).remaining_tokens == 4


async def test_retries_move_along_the_fallback_base_uris() -> None:
    async with await _kernel().boot() as booted:
        refused, answered = MockResponse(b"", {"http_code": 503}), MockResponse(b"ok")
        # Scripted before the client is built: walking base URIs narrows the
        # transport, and the narrowed copy answers from the script it was copied with.
        (await booted.container.get(MockHttpClient)).set_response_factory([refused, answered])
        client = await booted.container.get(HttpClientInterface, "fallback")

        async with await client.request("GET", "orders") as response:
            assert response.get_status_code() == 200

        assert refused.get_request_url() == "https://primary.test/orders"
        assert answered.get_request_url() == "https://secondary.test/orders"


async def test_a_named_retry_strategy_decides_what_is_made_again() -> None:
    async with await _kernel().boot() as booted:
        scripted = [MockResponse(b"", {"http_code": 418}), MockResponse(b"ok")]
        (await booted.container.get(MockHttpClient)).set_response_factory(scripted)
        client = await booted.container.get(HttpClientInterface, "teapot")

        async with await client.request("GET", "brew") as response:
            assert response.get_status_code() == 200


async def test_a_client_opting_out_of_the_mock_sends_through_the_real_transport() -> None:
    async with await _kernel().boot() as booted:
        real = await booted.container.get(HttpClientInterface, "real")
        github = await booted.container.get(HttpClientInterface, "github")

        assert _transport_of(real) is await booted.container.get(HttpxHttpClient)
        assert _transport_of(github) is await booted.container.get(MockHttpClient)


async def test_the_real_transport_is_closed_with_the_container() -> None:
    async with await _kernel().boot() as booted:
        transport = await booted.container.get(HttpxHttpClient)
        pool, _ = transport._clients.for_options(transport._default_options)

    assert pool.is_closed
