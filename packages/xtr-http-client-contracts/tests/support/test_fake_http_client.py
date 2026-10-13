from __future__ import annotations

import pytest

from tests.support.fake_http_client import FakeHttpClient
from tests.support.fake_response import FakeResponse
from xtr_http_client_contracts import HttpClientInterface

pytestmark = pytest.mark.anyio


def test_it_is_a_client() -> None:
    assert isinstance(FakeHttpClient(), HttpClientInterface)


async def test_a_request_answers_with_the_prepared_response() -> None:
    response = FakeResponse(status_code=201)
    client = FakeHttpClient(response)

    assert await client.request("POST", "https://example.com/orders") is response


async def test_every_call_is_recorded_with_the_options_it_was_made_with() -> None:
    client = FakeHttpClient()

    _ = await client.request("GET", "https://example.com/", timeout=2.5)

    assert client.calls == [("GET", "https://example.com/", {"timeout": 2.5})]


async def test_the_default_options_of_a_copy_reach_its_requests() -> None:
    client = FakeHttpClient().with_options(timeout=2.5, max_redirects=0)

    _ = await client.request("GET", "https://example.com/", timeout=10.0)

    assert client.calls == [("GET", "https://example.com/", {"timeout": 10.0, "max_redirects": 0})]


def test_a_copy_leaves_the_client_it_came_from_as_it_was() -> None:
    client = FakeHttpClient()

    copy = client.with_options(timeout=2.5)

    assert copy is not client
    assert client.default_options == {}
    assert copy.default_options == {"timeout": 2.5}
