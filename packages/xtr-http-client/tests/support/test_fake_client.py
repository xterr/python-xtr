from __future__ import annotations

import pytest
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_message import Request
from xtr_service_contracts import ResetInterface

from tests.support.fake_client import FakeClient
from xtr_http_client import MockResponse

pytestmark = pytest.mark.anyio

_URL = "http://example.com/foo-bar"


def test_it_is_a_client_and_not_one_that_can_be_reset() -> None:
    client = FakeClient()

    assert isinstance(client, HttpClientInterface)
    assert not isinstance(client, ResetInterface)


def test_narrowing_it_hands_back_the_client_it_was_asked_of() -> None:
    client = FakeClient()

    assert client.with_options(headers={"X-Fake": "yes"}) is client


async def test_a_request_is_answered_from_the_script() -> None:
    client = FakeClient([MockResponse(b"first"), MockResponse(b"second")])

    async with await client.request("GET", _URL) as response:
        assert await response.get_content() == b"first"

    async with await client.send_request(Request("GET", _URL)) as response:
        assert await response.get_content() == b"second"
