from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_client import (
    GenericRetryStrategy,
    MockHttpClient,
    RetryableHttpClient,
    ScopingHttpClient,
    TraceableHttpClient,
)
from xtr_http_client.bundle import HttpClientConfig, RetryFailedConfig, ScopedClientConfig
from xtr_http_client.bundle._clients import (
    _client_factory,
    _generic_strategy,
    _httpx_transport,
    _scoped,
)
from xtr_http_client.data_collector import HttpClientDataCollector

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_http_client import HttpxHttpClient

pytestmark = pytest.mark.anyio

_BASE_URI = "https://primary.test/"
_URL = "https://api.test/orders"


def _profiled_client(collector: HttpClientDataCollector, *, tracing: bool) -> TraceableHttpClient:
    client = _client_factory(None)(
        HttpClientConfig(tracing=tracing), MockHttpClient(), None, None, collector
    )
    assert isinstance(client, TraceableHttpClient)
    return client


async def _get(client: TraceableHttpClient) -> None:
    async with await client.request("GET", _URL):
        pass


def _clients_recorded(collector: HttpClientDataCollector) -> list[object]:
    requests = cast("list[dict[str, object]]", collector._read()["requests"])
    return [entry["client"] for entry in requests]


def test_an_unprofiled_untraced_client_is_left_unwrapped() -> None:
    transport = MockHttpClient()

    client = _client_factory(None)(HttpClientConfig(), transport, None, None, None)

    assert client is transport


async def test_a_client_traced_for_the_profiler_alone_keeps_only_profiled_requests() -> None:
    collector = HttpClientDataCollector()
    client = _profiled_client(collector, tracing=False)

    await _get(client)
    collector.begin_request()
    await _get(client)

    assert len(client.get_traced_requests()) == 1
    assert _clients_recorded(collector) == ["http_client"]


async def test_a_traced_client_profiled_too_keeps_every_request_and_hands_on_the_profiled() -> None:
    collector = HttpClientDataCollector()
    client = _profiled_client(collector, tracing=True)

    await _get(client)
    collector.begin_request()
    await _get(client)

    assert len(client.get_traced_requests()) == 2
    assert _clients_recorded(collector) == ["http_client"]


async def test_a_scoped_client_is_recorded_under_its_service_name() -> None:
    collector = HttpClientDataCollector()
    config = HttpClientConfig(scoped_clients={"github": ScopedClientConfig(base_uri=_BASE_URI)})
    client = _client_factory("github")(config, MockHttpClient(), None, None, collector)
    collector.begin_request()

    async with await client.request("GET", "repos"):
        pass

    assert _clients_recorded(collector) == ["http_client_github"]


async def test_the_real_transport_is_closed_when_its_factory_is() -> None:
    factory = cast("AsyncGenerator[HttpxHttpClient]", _httpx_transport(HttpClientConfig()))
    transport = await anext(factory)
    pool = transport._clients.for_options(transport._default_options)

    await factory.aclose()

    assert pool.is_closed


def test_retries_staying_on_one_base_uri_go_inside_the_scope() -> None:
    scoped = ScopedClientConfig(base_uri=_BASE_URI, retry_failed=RetryFailedConfig(enabled=True))

    client = _scoped(MockHttpClient(), scoped, None)

    assert isinstance(client, ScopingHttpClient)
    assert isinstance(client._client, RetryableHttpClient)


def test_retries_moving_along_base_uris_wrap_the_scope() -> None:
    retries = RetryFailedConfig(enabled=True, base_uris=("https://secondary.test/",))
    scoped = ScopedClientConfig(base_uri=_BASE_URI, retry_failed=retries)

    client = _scoped(MockHttpClient(), scoped, None)

    assert isinstance(client, RetryableHttpClient)
    assert isinstance(client._client, ScopingHttpClient)
    assert client._base_uris == (_BASE_URI, "https://secondary.test/")


def test_a_scope_is_also_the_default_one() -> None:
    client = _scoped(MockHttpClient(), ScopedClientConfig(scope=r"https://api\.test/"), None)

    assert isinstance(client, ScopingHttpClient)
    assert client._default_regexp == r"https://api\.test/"


def test_the_strategy_built_from_the_numbers_retries_the_codes_listed() -> None:
    strategy = _generic_strategy(RetryFailedConfig(enabled=True, http_codes={418: None}))

    assert isinstance(strategy, GenericRetryStrategy)
    assert strategy._status_codes == {418: None}
