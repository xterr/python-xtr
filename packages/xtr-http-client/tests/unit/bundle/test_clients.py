from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_client import (
    GenericRetryStrategy,
    MockHttpClient,
    RetryableHttpClient,
    ScopingHttpClient,
)
from xtr_http_client.bundle import HttpClientConfig, RetryFailedConfig, ScopedClientConfig
from xtr_http_client.bundle._clients import _generic_strategy, _httpx_transport, _scoped

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_http_client import HttpxHttpClient

pytestmark = pytest.mark.anyio

_BASE_URI = "https://primary.test/"


async def test_the_real_transport_is_closed_when_its_factory_is() -> None:
    factory = cast("AsyncGenerator[HttpxHttpClient, None]", _httpx_transport(HttpClientConfig()))
    transport = await anext(factory)
    pool, _ = transport._clients.for_options(transport._default_options)

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
