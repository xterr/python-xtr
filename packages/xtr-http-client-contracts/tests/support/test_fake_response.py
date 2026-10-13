from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface

from tests.support.fake_response import FakeResponse
from tests.support.fake_stream import FakeStream
from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    RedirectionError,
    ServerError,
    TransportError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

INFO_KEYS = {
    "canceled",
    "error",
    "http_code",
    "http_method",
    "redirect_count",
    "redirect_url",
    "response_headers",
    "start_time",
    "total_time",
    "url",
    "user_data",
}


def _info(response: FakeResponse) -> Mapping[str, object]:
    return cast("Mapping[str, object]", response.get_info())


def test_it_is_a_message_response() -> None:
    assert isinstance(FakeResponse(), MessageResponseInterface)


async def test_the_body_is_read_through_the_stream_or_in_one_call() -> None:
    response = FakeResponse(body=FakeStream(b"hello"))

    assert await response.get_body().read(5) == b"hello"
    assert await response.get_content() == b"hello"


def test_a_header_is_found_whatever_case_it_is_asked_for_in() -> None:
    response = FakeResponse(headers={"Content-Type": ("application/json",)})

    assert response.has_header("content-type")
    assert response.get_header("CONTENT-TYPE") == ("application/json",)
    assert response.get_header_line("content-type") == "application/json"
    assert response.get_header("absent") == ()
    assert response.get_header_line("absent") == ""


def test_a_copy_keeps_the_transfer_info_and_the_very_same_body() -> None:
    body = FakeStream(b"hello")
    response = FakeResponse(body=body, user_data={"attempt": 1})

    copy = response.with_header("x-trace", "abc")

    assert copy.get_body() is body
    assert copy.get_info("user_data") == {"attempt": 1}
    assert copy.get_info("url") == response.get_info("url")
    assert copy.get_info("http_code") == response.get_info("http_code")
    assert copy.get_header("x-trace") == ("abc",)
    assert not response.has_header("x-trace")


def test_adding_to_a_header_keeps_the_case_it_was_first_given_in() -> None:
    response = FakeResponse(headers={"Set-Cookie": ("a=1",)})

    copy = response.with_added_header("set-cookie", "b=2")

    assert copy.get_headers() == {"Set-Cookie": ("a=1", "b=2")}


def test_dropping_a_header_leaves_the_others() -> None:
    response = FakeResponse(headers={"Content-Type": ("text/plain",), "X-Trace": ("abc",)})

    copy = response.without_header("content-type")

    assert copy.get_headers() == {"X-Trace": ("abc",)}


def test_the_status_and_the_protocol_version_are_carried_by_copies() -> None:
    response = FakeResponse()

    assert response.get_status_code() == 200
    assert response.get_reason_phrase() == "OK"
    assert response.get_protocol_version() == "1.1"

    moved = response.with_status(404, "Not Found").with_protocol_version("2")

    assert moved.get_status_code() == 404
    assert moved.get_reason_phrase() == "Not Found"
    assert moved.get_protocol_version() == "2"


async def test_the_body_a_copy_was_given_replaces_the_one_it_came_with() -> None:
    response = FakeResponse(body=FakeStream(b"old"))

    copy = response.with_body(FakeStream(b"new"))

    assert await copy.get_content() == b"new"


def test_the_info_always_carries_every_key_the_contract_names() -> None:
    assert set(_info(FakeResponse())) == INFO_KEYS


def test_one_info_entry_can_be_asked_for_and_an_unknown_one_reads_as_none() -> None:
    response = FakeResponse(status_code=201, user_data="ticket-7")

    assert response.get_info("http_code") == 201
    assert response.get_info("user_data") == "ticket-7"
    assert response.get_info("primary_ip") is None


def test_the_response_headers_are_the_raw_status_and_header_lines() -> None:
    response = FakeResponse(headers={"Set-Cookie": ("a=1", "b=2")})

    assert response.get_info("response_headers") == [
        "HTTP/1.1 200 OK",
        "Set-Cookie: a=1",
        "Set-Cookie: b=2",
    ]


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(302, RedirectionError), (404, ClientError), (500, ServerError)],
)
async def test_reading_the_content_raises_for_a_status_that_is_not_a_success(
    status_code: int,
    expected: type[Exception],
) -> None:
    response = FakeResponse(status_code=status_code, body=FakeStream(b"nope"))

    with pytest.raises(expected) as raised:
        _ = await response.get_content()

    assert str(raised.value) == f'HTTP {status_code} returned for "https://example.com/".'


async def test_asking_not_to_throw_returns_the_body_of_a_failed_request() -> None:
    response = FakeResponse(status_code=404, body=FakeStream(b"nope"))

    assert await response.get_content(throw=False) == b"nope"


async def test_a_json_object_decodes_to_a_mapping() -> None:
    response = FakeResponse(body=FakeStream(b'{"id": 7}'))

    assert await response.to_array() == {"id": 7}


@pytest.mark.parametrize("body", [b"[1, 2]", b"not json"])
async def test_a_body_that_is_not_a_json_object_is_refused(body: bytes) -> None:
    response = FakeResponse(body=FakeStream(body))

    with pytest.raises(DecodingError):
        _ = await response.to_array()


async def test_cancelling_lets_go_of_the_body_and_shows_in_the_info() -> None:
    body = FakeStream(b"hello")
    response = FakeResponse(body=body)

    await response.cancel()

    assert body.closed
    assert response.get_info("canceled") is True
    assert response.get_info("error") == "Response has been canceled."


async def test_reading_a_cancelled_response_raises_the_cancellation() -> None:
    response = FakeResponse(body=FakeStream(b"hello"))
    await response.cancel()

    with pytest.raises(TransportError, match="Response has been canceled"):
        _ = await response.get_content()


async def test_leaving_the_block_closes_the_body() -> None:
    body = FakeStream(b"hello")

    async with FakeResponse(body=body) as response:
        assert response.get_status_code() == 200

    assert body.closed
