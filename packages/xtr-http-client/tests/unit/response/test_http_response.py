from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_message import Response, Stream

from xtr_http_client import HttpResponse
from xtr_http_client.exception import (
    ClientError,
    JsonError,
    RedirectionError,
    ServerError,
    TransportError,
)
from xtr_http_client.internal.response_body import ResponseBody

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence

pytestmark = pytest.mark.anyio

URL = "https://example.com/orders"


async def arriving(*pieces: bytes) -> AsyncIterator[bytes]:
    for piece in pieces:
        yield piece


@final
class Responses:
    """Makes responses and lets go of every body when the test is over.

    A body holds a temporary file, so a test that leaves one behind leaves the
    file behind too; closing them all here is what leaving the response's own
    block does.
    """

    def __init__(self) -> None:
        self._made: list[HttpResponse] = []

    def of(
        self,
        status: int = 200,
        *pieces: bytes,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        on_cancel: Callable[[], Awaitable[None]] | None = None,
    ) -> HttpResponse:
        info: dict[str, object] = {
            "canceled": False,
            "error": None,
            "http_code": status,
            "url": URL,
        }
        response = HttpResponse(
            Response(status, headers),
            ResponseBody(arriving(*pieces)),
            info,
            on_cancel,
        )
        self._made.append(response)
        return response

    async def close(self) -> None:
        for response in self._made:
            await response.get_body().close()


@pytest.fixture
async def responses() -> AsyncIterator[Responses]:
    made = Responses()
    try:
        yield made
    finally:
        await made.close()


async def test_the_status_line_is_the_messages(responses: Responses) -> None:
    response = responses.of(201)

    assert response.get_status_code() == 201
    assert response.get_reason_phrase() == "Created"
    assert response.get_protocol_version() == "1.1"


async def test_the_headers_are_the_messages(responses: Responses) -> None:
    response = responses.of(200, headers={"Content-Type": "application/json", "X-Try": ["1", "2"]})

    assert set(response.get_headers()) == {"Content-Type", "X-Try"}
    assert response.has_header("content-type")
    assert list(response.get_header("content-type")) == ["application/json"]
    assert response.get_header_line("x-try") == "1, 2"
    assert list(response.get_header("x-missing")) == []


async def test_a_copy_carries_the_change_and_leaves_this_one_as_it_was(
    responses: Responses,
) -> None:
    response = responses.of(200)

    copy = response.with_status(404, "Nope").with_protocol_version("2")

    assert (copy.get_status_code(), copy.get_reason_phrase()) == (404, "Nope")
    assert copy.get_protocol_version() == "2"
    assert (response.get_status_code(), response.get_protocol_version()) == (200, "1.1")


async def test_a_copy_keeps_the_body_and_the_info(responses: Responses) -> None:
    response = responses.of(200, b"hello")

    copy = response.with_header("x-try", "1")

    assert copy.get_body() is response.get_body()
    assert copy.get_info("url") == URL
    assert await copy.get_content() == b"hello"


async def test_a_header_is_added_to_and_dropped_from_a_copy(responses: Responses) -> None:
    response = responses.of(200, headers={"X-Gone": "1"})

    copy = (
        response.with_header("x-try", "1").with_added_header("x-try", "2").without_header("x-gone")
    )

    assert copy.get_header_line("x-try") == "1, 2"
    assert not copy.has_header("x-gone")
    assert response.has_header("x-gone")


async def test_with_body_reads_the_given_stream_instead(responses: Responses) -> None:
    response = responses.of(200, b"arriving")
    replacement = Stream.create(b"replaced")

    copy = response.with_body(replacement)

    assert copy.get_body() is replacement
    assert await copy.get_content() == b"replaced"
    assert await response.get_content() == b"arriving"


async def test_the_info_is_handed_over_as_a_copy(responses: Responses) -> None:
    response = responses.of(200)

    first = response.get_info()

    assert first == {"canceled": False, "error": None, "http_code": 200, "url": URL}
    assert first is not response.get_info()


async def test_one_entry_of_the_info_is_read_by_name(responses: Responses) -> None:
    response = responses.of(200)

    assert response.get_info("url") == URL


async def test_an_entry_the_info_has_not_got_reads_as_nothing(responses: Responses) -> None:
    response = responses.of(200)

    assert response.get_info("primary_ip") is None


async def test_the_whole_body_is_read_from_the_pieces_it_arrived_in(responses: Responses) -> None:
    response = responses.of(200, b"hel", b"lo")

    assert await response.get_content() == b"hello"


async def test_the_body_can_be_read_again(responses: Responses) -> None:
    response = responses.of(200, b"hel", b"lo")

    assert await response.get_content() == b"hello"
    assert await response.get_content() == b"hello"


async def test_a_4xx_is_raised_as_a_client_error(responses: Responses) -> None:
    response = responses.of(404, b"nope")

    with pytest.raises(ClientError) as caught:
        _ = await response.get_content()

    assert caught.value.reason == f'HTTP 404 returned for "{URL}".'
    assert caught.value.response is response


async def test_a_5xx_is_raised_as_a_server_error(responses: Responses) -> None:
    response = responses.of(503, b"down")

    with pytest.raises(ServerError) as caught:
        _ = await response.get_content()

    assert caught.value.reason == f'HTTP 503 returned for "{URL}".'


async def test_a_3xx_is_raised_as_a_redirection_error(responses: Responses) -> None:
    response = responses.of(301, b"elsewhere")

    with pytest.raises(RedirectionError) as caught:
        _ = await response.get_content()

    assert caught.value.reason == f'HTTP 301 returned for "{URL}".'


async def test_an_unsuccessful_status_is_answered_with_its_body_when_asked(
    responses: Responses,
) -> None:
    response = responses.of(404, b"nope")

    assert await response.get_content(throw=False) == b"nope"


async def test_a_json_object_is_decoded(responses: Responses) -> None:
    response = responses.of(200, b'{"id": 7}')

    assert await response.to_array() == {"id": 7}


async def test_an_empty_body_is_no_json_object(responses: Responses) -> None:
    response = responses.of(200)

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert caught.value.reason == "Response body is empty."


async def test_a_body_that_is_not_json_names_the_url_it_came_from(responses: Responses) -> None:
    response = responses.of(200, b"not json at all")

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert caught.value.reason.endswith(f'for "{URL}".')


async def test_json_that_is_not_an_object_names_what_it_decoded_to(responses: Responses) -> None:
    response = responses.of(200, b"[1, 2]")

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert caught.value.reason == (
        f'JSON content was expected to decode to an array, "list" returned for "{URL}".'
    )


async def test_cancelling_records_why_and_refuses_the_body_afterwards(
    responses: Responses,
) -> None:
    response = responses.of(200, b"hello")

    await response.cancel()

    assert response.get_info("canceled") is True
    assert response.get_info("error") == "Response has been canceled."

    with pytest.raises(TransportError) as caught:
        _ = await response.get_content()

    assert caught.value.reason == "Response has been canceled."


async def test_cancelling_abandons_the_transfer_behind_the_response(
    responses: Responses,
) -> None:
    abandoned: list[str] = []

    async def abandon() -> None:
        abandoned.append("transfer")

    response = responses.of(200, b"hello", on_cancel=abandon)

    await response.cancel()

    assert abandoned == ["transfer"]


async def test_a_body_that_will_not_read_is_reported_as_a_transport_error(
    responses: Responses,
) -> None:
    response = responses.of(200, b"hello")
    await response.get_body().close()

    with pytest.raises(TransportError) as caught:
        _ = await response.get_content()

    assert caught.value.reason == "The response body is closed."


async def test_leaving_the_block_closes_the_body(responses: Responses) -> None:
    response = responses.of(200, b"hello")

    async with response as entered:
        assert entered is response
        assert await entered.get_content() == b"hello"

    assert not response.get_body().is_readable()
