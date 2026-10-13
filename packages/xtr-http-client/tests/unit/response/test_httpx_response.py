from __future__ import annotations

import gzip
from typing import TYPE_CHECKING, cast, final

import anyio
import anyio.lowlevel
import httpx
import pytest

from xtr_http_client.response import to_http_response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

pytestmark = pytest.mark.anyio

_REQUEST = httpx.Request("GET", "http://example.test")


@final
class _FakeConnection:
    """A connection that answers one thing about itself, as the record asks it to."""

    def __init__(self, server_addr: object) -> None:
        self._server_addr = server_addr

    def get_extra_info(self, info: str) -> object:
        return self._server_addr if info == "server_addr" else None


async def _pieces(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        await anyio.lowlevel.checkpoint()
        yield part


async def test_the_status_line_and_headers_become_the_message() -> None:
    response = await to_http_response(
        httpx.Response(
            404,
            headers={"Content-Type": "application/json"},
            content=b"{}",
            request=_REQUEST,
        ),
        [],
        "GET",
        0.0,
        None,
    )

    assert response.get_status_code() == 404
    assert response.get_reason_phrase() == "Not Found"
    assert response.get_protocol_version() == "1.1"
    assert response.get_header("content-type") == ["application/json"]


async def test_the_record_says_what_the_transfer_was_and_what_it_carried() -> None:
    data = object()
    response = await to_http_response(
        httpx.Response(200, content=b"", request=_REQUEST),
        [],
        "HEAD",
        1234.5,
        data,
    )
    info = response.get_info()

    assert info == {
        "canceled": False,
        "error": None,
        "http_code": 200,
        "http_method": "HEAD",
        "redirect_count": 0,
        "redirect_url": None,
        "response_headers": ["HTTP/1.1 200 OK"],
        "start_time": 1234.5,
        "total_time": response.get_info("total_time"),
        "url": "http://example.test/",
        "user_data": data,
    }


async def test_the_empty_path_of_a_url_is_written_as_the_root_it_means() -> None:
    response = await to_http_response(
        httpx.Response(200, content=b"", request=_REQUEST),
        [],
        "GET",
        0.0,
        None,
    )

    assert response.get_info("url") == "http://example.test/"


async def test_every_hop_leaves_its_status_line_and_headers_in_the_record() -> None:
    moved = httpx.Response(
        301,
        headers={"Location": "http://example.test/here"},
        content=b"",
        request=_REQUEST,
    )
    response = await to_http_response(
        httpx.Response(200, content=b"", request=_REQUEST),
        [moved],
        "GET",
        0.0,
        None,
    )

    assert response.get_info("redirect_count") == 1
    assert response.get_info("response_headers") == [
        "HTTP/1.1 301 Moved Permanently",
        "Location: http://example.test/here",
        "HTTP/1.1 200 OK",
    ]


async def test_a_redirect_nobody_followed_says_where_it_points() -> None:
    moved = httpx.Response(
        302,
        headers={"Location": "/elsewhere"},
        content=b"",
        request=_REQUEST,
    )
    moved.next_request = httpx.Request("GET", "http://example.test/elsewhere")

    response = await to_http_response(moved, [], "GET", 0.0, None)

    assert response.get_info("redirect_url") == "http://example.test/elsewhere"


async def test_a_header_sent_twice_in_two_cases_keeps_the_case_it_came_in_first() -> None:
    answer = httpx.Response(200, content=b"", request=_REQUEST)
    answer.headers = httpx.Headers([("Set-Cookie", "a=1"), ("set-cookie", "b=2")])

    response = await to_http_response(answer, [], "GET", 0.0, None)

    assert response.get_headers() == {"Set-Cookie": ["a=1", "b=2"]}


async def test_a_body_is_handed_over_decoded() -> None:
    answer = httpx.Response(
        200,
        headers={"Content-Encoding": "gzip"},
        content=_pieces(gzip.compress(b"orders")),
        request=_REQUEST,
    )

    async with await to_http_response(answer, [], "GET", 0.0, None) as response:
        assert await response.get_content() == b"orders"


async def test_a_body_whose_encoding_was_asked_for_is_handed_over_as_it_arrived() -> None:
    compressed = gzip.compress(b"orders")
    answer = httpx.Response(
        200,
        headers={"Content-Encoding": "gzip"},
        content=_pieces(compressed),
        request=_REQUEST,
    )

    async with await to_http_response(answer, [], "GET", 0.0, None, decode=False) as response:
        assert await response.get_content() == compressed


async def test_the_address_the_answer_came_from_is_recorded_when_it_is_known() -> None:
    answer = httpx.Response(
        200,
        content=b"",
        request=_REQUEST,
        extensions={"network_stream": _FakeConnection(("93.184.216.34", 80))},
    )

    response = await to_http_response(answer, [], "GET", 0.0, None)

    assert response.get_info("primary_ip") == "93.184.216.34"


@pytest.mark.parametrize("server_addr", [None, "93.184.216.34", (), (80, "example.test")])
async def test_an_address_the_connection_cannot_name_is_left_out(server_addr: object) -> None:
    answer = httpx.Response(
        200,
        content=b"",
        request=_REQUEST,
        extensions={"network_stream": _FakeConnection(server_addr)},
    )

    response = await to_http_response(answer, [], "GET", 0.0, None)

    assert "primary_ip" not in cast("Mapping[str, object]", response.get_info())


async def test_no_address_is_recorded_when_there_is_no_connection_to_ask() -> None:
    response = await to_http_response(
        httpx.Response(200, content=b"", request=_REQUEST),
        [],
        "GET",
        0.0,
        None,
    )

    assert response.get_info("primary_ip") is None
