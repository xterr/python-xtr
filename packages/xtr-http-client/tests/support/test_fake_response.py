from __future__ import annotations

import pytest
from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    HttpResponseInterface,
    ServerError,
)
from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface

from tests.support.fake_response import FakeResponse
from tests.support.fake_stream import FakeStream

pytestmark = pytest.mark.anyio


def test_it_is_a_client_response_and_a_message_response() -> None:
    response = FakeResponse()

    assert isinstance(response, HttpResponseInterface)
    assert isinstance(response, MessageResponseInterface)


def test_the_head_it_was_built_with_is_what_the_info_answers() -> None:
    response = FakeResponse(
        status_code=400,
        url="http://example.com",
        response_headers=["HTTP/1.1 400 Bad Request", "Content-Type: application/json"],
    )

    assert response.get_info("http_code") == 400
    assert response.get_info("url") == "http://example.com"
    assert response.get_info("response_headers") == [
        "HTTP/1.1 400 Bad Request",
        "Content-Type: application/json",
    ]
    assert response.get_info("primary_ip") is None


async def test_every_read_of_the_content_is_counted() -> None:
    response = FakeResponse(body=FakeStream(b"nope"), status_code=400)

    assert await response.get_content(throw=False) == b"nope"
    assert await response.get_content(throw=False) == b"nope"
    assert response.content_reads == 2


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(404, ClientError), (500, ServerError)],
)
async def test_reading_the_content_raises_for_a_status_that_is_not_a_success(
    status_code: int,
    expected: type[Exception],
) -> None:
    response = FakeResponse(status_code=status_code, body=FakeStream(b"nope"))

    with pytest.raises(expected):
        _ = await response.get_content()


async def test_a_json_object_body_decodes_to_a_mapping() -> None:
    response = FakeResponse(body=FakeStream(b'{"id": 7}'))

    assert await response.to_array() == {"id": 7}

    with pytest.raises(DecodingError):
        _ = await FakeResponse(body=FakeStream(b"[1]")).to_array()


async def test_the_body_is_also_readable_as_a_stream() -> None:
    response = FakeResponse(body=FakeStream(b"hello"))

    assert await response.get_body().get_contents() == b"hello"


async def test_a_copy_keeps_the_head_and_the_very_same_body() -> None:
    body = FakeStream(b"hello")
    response = FakeResponse(body=body, headers={"X-Trace": ("abc",)})

    copy = response.with_header("x-run", "7").with_status(201, "Created")

    assert copy.get_body() is body
    assert copy.get_header("x-trace") == ("abc",)
    assert copy.get_status_code() == 201
    assert await copy.get_content() == b"hello"


async def test_cancelling_lets_go_of_the_body_and_shows_in_the_info() -> None:
    body = FakeStream(b"hello")
    response = FakeResponse(body=body)

    await response.cancel()

    assert body.closed
    assert response.get_info("canceled") is True


async def test_leaving_the_block_closes_the_body() -> None:
    body = FakeStream(b"hello")

    async with FakeResponse(body=body) as response:
        assert response.get_status_code() == 200

    assert body.closed
