from __future__ import annotations

import pytest
from xtr_http_message import Request

from tests.support.fake_client import FakeClient
from tests.support.fake_stream import FakeStream
from xtr_http_client import MockHttpClient, MockResponse, TraceableHttpClient
from xtr_http_client.exception import ClientError, TransportError

pytestmark = pytest.mark.anyio

_URL = "https://example.com/foo/bar"


async def test_a_request_is_written_down_as_it_was_made() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"hello")))

    async with await client.request("GET", _URL, headers={"X-Kind": "thing"}) as response:
        assert await response.get_content() == b"hello"

    traced = client.get_traced_requests()

    assert len(traced) == 1
    assert traced[0]["method"] == "GET"
    assert traced[0]["url"] == _URL
    assert traced[0]["options"] == {"headers": {"X-Kind": "thing"}}
    assert traced[0]["content"] == b"hello"


async def test_a_sent_request_is_written_down_by_its_method_and_uri() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"sent")))

    async with await client.send_request(Request("POST", _URL)) as response:
        assert await response.get_content() == b"sent"

    traced = client.get_traced_requests()

    assert len(traced) == 1
    assert traced[0]["method"] == "POST"
    assert traced[0]["url"] == _URL
    assert traced[0]["content"] == b"sent"


async def test_what_the_transfer_knows_about_itself_is_written_down() -> None:
    client = TraceableHttpClient(MockHttpClient())

    async with await client.request("GET", _URL):
        pass

    info = client.get_traced_requests()[0]["info"]

    assert info["http_method"] == "GET"
    assert info["url"] == _URL
    assert info["http_code"] == 200


async def test_a_body_nobody_read_is_written_down_as_unread() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"hello")))

    async with await client.request("GET", _URL):
        pass

    assert client.get_traced_requests()[0]["content"] is None


async def test_a_body_read_as_json_is_written_down_as_the_bytes_it_was() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b'{"id": 7}')))

    async with await client.request("GET", _URL) as response:
        assert await response.to_array() == {"id": 7}

    assert client.get_traced_requests()[0]["content"] == b'{"id": 7}'


async def test_a_body_read_as_json_is_still_checked_for_its_status_first() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"Errored.", {"http_code": 400})))

    async with await client.request("GET", _URL) as response:
        with pytest.raises(ClientError):
            _ = await response.to_array()

    assert client.get_traced_requests()[0]["content"] is None


async def test_the_bodies_are_left_out_when_a_request_asks_for_that() -> None:
    client = TraceableHttpClient(MockHttpClient([MockResponse(b"hello"), MockResponse()]))

    async with await client.request(
        "POST",
        _URL,
        body=b"sent",
        extra={"trace_content": False},
    ) as response:
        assert await response.get_content() == b"hello"
    async with await client.request("POST", _URL, json={"id": 7}, extra={"trace_content": False}):
        pass

    traced = client.get_traced_requests()

    assert traced[0]["options"] == {"extra": {"trace_content": False}}
    assert traced[0]["content"] is False
    assert traced[1]["options"] == {"extra": {"trace_content": False}}
    assert traced[1]["content"] is False


async def test_an_extra_that_says_nothing_about_the_bodies_keeps_them() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"hello")))

    async with await client.request("GET", _URL, extra={"other": True}) as response:
        assert await response.get_content() == b"hello"

    assert client.get_traced_requests()[0]["content"] == b"hello"


async def test_a_request_that_brought_back_nothing_is_written_down_with_why() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(info={"error": "Refused."})))

    with pytest.raises(TransportError, match="Refused"):
        _ = await client.request("GET", _URL)

    traced = client.get_traced_requests()

    assert traced[0]["info"] == {"error": "Refused."}
    assert traced[0]["content"] is None


async def test_a_request_made_while_tracing_is_off_is_only_passed_on() -> None:
    switched_off = True
    client = TraceableHttpClient(
        MockHttpClient([MockResponse(b"first"), MockResponse(b"second")]),
        lambda: switched_off,
    )

    async with await client.request("GET", _URL) as response:
        assert await response.get_content() == b"first"

    assert client.get_traced_requests() == []

    switched_off = False
    async with await client.send_request(Request("GET", _URL)) as response:
        assert await response.get_content() == b"second"

    assert len(client.get_traced_requests()) == 1


async def test_a_sent_request_made_while_tracing_is_off_is_only_passed_on() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"sent")), lambda: True)

    async with await client.send_request(Request("GET", _URL)) as response:
        assert await response.get_content() == b"sent"

    assert client.get_traced_requests() == []


async def test_the_record_handed_over_is_not_the_one_the_client_appends_to() -> None:
    client = TraceableHttpClient(MockHttpClient())

    async with await client.request("GET", _URL):
        pass

    taken = client.get_traced_requests()
    taken.clear()

    assert len(client.get_traced_requests()) == 1


async def test_a_narrowed_client_writes_into_the_same_record() -> None:
    client = TraceableHttpClient(MockHttpClient([MockResponse(), MockResponse()]))

    narrowed = client.with_options(base_uri="https://example.org")
    async with await narrowed.request("GET", "/orders"):
        pass
    async with await client.request("GET", _URL):
        pass

    traced = client.get_traced_requests()

    assert narrowed is not client
    assert narrowed.get_traced_requests() == traced
    assert len(traced) == 2
    assert traced[0]["info"]["url"] == "https://example.org/orders"


async def test_resetting_forgets_every_request_written_down() -> None:
    client = TraceableHttpClient(MockHttpClient())

    async with await client.request("GET", _URL):
        pass
    await client.reset()

    assert client.get_traced_requests() == []


async def test_resetting_forgets_what_a_narrowed_client_wrote_down_too() -> None:
    client = TraceableHttpClient(MockHttpClient())
    narrowed = client.with_options(headers={"X-Kind": "thing"})

    async with await narrowed.request("GET", _URL):
        pass
    await client.reset()

    assert narrowed.get_traced_requests() == []


async def test_resetting_reaches_a_wrapped_client_that_can_be_reset() -> None:
    inner = MockHttpClient()
    client = TraceableHttpClient(inner)

    async with await client.request("GET", _URL):
        pass
    await client.reset()

    assert inner.get_requests_count() == 0


async def test_resetting_leaves_a_wrapped_client_that_cannot_be_reset_alone() -> None:
    client = TraceableHttpClient(FakeClient())

    async with await client.request("GET", _URL):
        pass
    await client.reset()

    assert client.get_traced_requests() == []


async def test_the_response_handed_back_reads_as_the_wrapped_one_does() -> None:
    inner = MockResponse(b"payload", {"response_headers": {"X-Kind": "thing"}})
    client = TraceableHttpClient(MockHttpClient(inner))

    async with await client.request("GET", _URL) as response:
        assert response.get_status_code() == 200
        assert response.get_reason_phrase() == "OK"
        assert response.get_protocol_version() == "1.1"
        assert response.has_header("x-kind")
        assert list(response.get_header("x-kind")) == ["thing"]
        assert response.get_header_line("x-kind") == "thing"
        assert "X-Kind" in response.get_headers()
        assert response.get_info("http_code") == 200
        assert response.get_body() is inner.get_body()


async def test_a_copy_of_the_response_writes_into_the_record_as_well() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"payload")))

    async with await client.request("GET", _URL) as response:
        copies = (
            response.with_status(500),
            response.with_protocol_version("2"),
            response.with_header("X-Kind", "thing"),
            response.with_added_header("X-Kind", "other"),
            response.without_header("X-Kind"),
            response.with_body(FakeStream(b"replaced")),
        )

        for copy in copies:
            assert copy is not response
        assert await copies[2].get_content() == b"payload"

    assert client.get_traced_requests()[0]["content"] == b"payload"


async def test_cancelling_cancels_the_wrapped_transfer() -> None:
    client = TraceableHttpClient(MockHttpClient(MockResponse(b"payload")))

    response = await client.request("GET", _URL)
    await response.cancel()

    assert response.get_info("canceled") is True
