from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest
from xtr_http_client_contracts import HttpError, ResponseInterface
from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface

from tests.support.fake_backend import URL, FakeBackend, FakeBackends
from tests.support.fake_response import FakeResponse
from xtr_http_client.chunk import ErrorChunk, InformationalChunk
from xtr_http_client.exception import (
    ClientError,
    JsonError,
    RedirectionError,
    ServerError,
    TransportError,
    TransportTimeoutError,
)
from xtr_http_client.response.http_client_response import HttpClientResponse

if TYPE_CHECKING:
    from xtr_http_client_contracts import ChunkInterface

    from xtr_http_client.response.response_stream import ResponseStream

pytestmark = pytest.mark.anyio

JSON = {"Content-Type": "application/json"}


def describe(chunk: ChunkInterface) -> str | bytes:
    if chunk.get_error() is not None:
        return "timeout" if chunk.is_timeout() else "error"
    if chunk.is_first():
        return "first"
    if chunk.is_last():
        return "last"
    return chunk.get_content()


async def run(stream: ResponseStream) -> list[str | bytes]:
    with anyio.fail_after(1):
        return [describe(chunk) async for _response, chunk in stream]


def test_it_is_a_client_response_and_an_http_response() -> None:
    response = FakeBackend().response

    assert isinstance(response, ResponseInterface)
    assert isinstance(response, MessageResponseInterface)


async def test_its_body_is_read_off_the_transfer(backends: FakeBackends) -> None:
    response = backends.make().answer(b"abc", b"def")

    assert await response.get_body().get_contents() == b"abcdef"


def test_the_info_is_reported_whole_or_by_entry() -> None:
    backend = FakeBackend(404)

    assert backend.response.get_info() == backend.info
    assert backend.response.get_info("http_code") == 404
    assert backend.response.get_info("nothing-of-the-sort") is None


def test_the_info_handed_out_cannot_change_the_response() -> None:
    backend = FakeBackend()
    info = backend.response.get_info()
    assert isinstance(info, dict)

    info["url"] = "https://elsewhere.example/"

    assert backend.response.get_info("url") == URL


def test_the_info_shows_what_the_backend_records_later() -> None:
    backend = FakeBackend()

    backend.info["primary_ip"] = "127.0.0.1"

    assert backend.response.get_info("primary_ip") == "127.0.0.1"


def test_the_info_reports_what_broke_the_transfer() -> None:
    backend = FakeBackend()

    backend.transfer.fail(OSError("Connection reset by peer"))

    assert backend.response.get_info("error") == "Connection reset by peer"


async def test_a_copy_keeps_the_info_and_the_body(backends: FakeBackends) -> None:
    backend = backends.make()
    response = backend.answer(b"abc")

    copy = response.with_header("X-Copy", "1")
    backend.info["primary_ip"] = "127.0.0.1"

    assert copy.get_info("primary_ip") == "127.0.0.1"
    assert copy.get_body() is response.get_body()
    assert await copy.get_content() == b"abc"
    assert await response.get_content() == b"abc"
    assert not response.has_header("x-copy")


async def test_reading_the_content_waits_for_the_whole_body(backends: FakeBackends) -> None:
    backend = backends.make()
    contents: list[bytes] = []

    async def read() -> None:
        contents.append(await backend.response.get_content())

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(read)
            backend.send(b"abc")
            await anyio.wait_all_tasks_blocked()
            _ = backend.answer(b"def")

    assert contents == [b"abcdef"]


async def test_a_kept_body_reads_the_same_twice(backends: FakeBackends) -> None:
    response = backends.make().answer(b"abc")

    assert await response.get_content() == b"abc"
    assert await response.get_content() == b"abc"


async def test_a_body_not_kept_cannot_be_read_twice(backends: FakeBackends) -> None:
    response = backends.make(buffered=False).answer(b"abc")
    assert await response.get_content() == b"abc"

    with pytest.raises(TransportError) as caught:
        _ = await response.get_content()

    assert str(caught.value) == (
        "Cannot get the content of the response twice: buffering is disabled."
    )


async def test_an_empty_body_reads_twice_even_when_not_kept(backends: FakeBackends) -> None:
    response = backends.make(buffered=False).answer()

    assert await response.get_content() == b""
    assert await response.get_content() == b""


@pytest.mark.parametrize(
    ("status", "error"),
    [(301, RedirectionError), (404, ClientError), (503, ServerError)],
)
async def test_reading_the_content_raises_for_an_unsuccessful_status(
    backends: FakeBackends,
    status: int,
    error: type[HttpError],
) -> None:
    response = backends.make(status).answer(b"nope")

    with pytest.raises(error) as caught:
        _ = await response.get_content()

    assert caught.value.response is response
    assert str(caught.value) == (
        f'HTTP/1.1 {status} {response.get_reason_phrase()} returned for "{URL}".'
    )


async def test_an_unsuccessful_status_is_read_when_not_thrown(backends: FakeBackends) -> None:
    response = backends.make(404).answer(b"not here")

    assert await response.get_content(throw=False) == b"not here"


async def test_an_error_document_names_the_problem(backends: FakeBackends) -> None:
    backend = backends.make(400, {"Content-Type": "application/problem+json"})
    response = backend.answer(b'{"title": "Bad Request", "detail": "The id is missing."}')

    with pytest.raises(ClientError) as caught:
        _ = await response.get_content()

    assert str(caught.value) == "Bad Request\n\nThe id is missing."


async def test_reading_the_content_raises_what_broke_the_transfer(backends: FakeBackends) -> None:
    backend = backends.make()
    backend.send(b"abc")
    backend.transfer.fail(OSError("Connection reset by peer"))

    with pytest.raises(TransportError, match="Connection reset by peer"):
        _ = await backend.response.get_content()


async def test_reading_carries_on_after_the_transfer_went_quiet(backends: FakeBackends) -> None:
    backend = backends.make()
    backend.send(b"<1>")
    backend.transfer.push(backend.transfer.idle_chunk(URL, 0.1))
    _ = backend.answer(b"<2>")

    with pytest.raises(TransportTimeoutError):
        _ = await backend.response.get_content()

    assert await backend.response.get_content() == b"<1><2>"


async def test_reading_gives_up_once_the_idle_timeout_passes(backends: FakeBackends) -> None:
    backend = backends.make(timeout=0.01)
    backend.send(b"<1>")

    with anyio.fail_after(1), pytest.raises(TransportTimeoutError) as caught:
        _ = await backend.response.get_content()

    assert str(caught.value) == f'Idle timeout reached for "{URL}".'


async def test_a_json_object_is_decoded(backends: FakeBackends) -> None:
    response = backends.make(200, JSON).answer(b'{"id": 7, "tags": ["a"]}')

    assert await response.to_array() == {"id": 7, "tags": ["a"]}


async def test_a_kept_body_is_decoded_once(backends: FakeBackends) -> None:
    response = backends.make(200, JSON).answer(b'{"id": 7}')

    assert await response.to_array() is await response.to_array()


async def test_an_empty_body_is_not_json(backends: FakeBackends) -> None:
    response = backends.make().answer()

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert str(caught.value) == "Response body is empty."


async def test_a_body_that_is_not_json_says_where_it_came_from(backends: FakeBackends) -> None:
    response = backends.make().answer(b"{oops")

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert str(caught.value).endswith(f' for "{URL}".')


@pytest.mark.parametrize(
    ("body", "kind"),
    [(b"[1, 2]", "list"), (b'"text"', "str"), (b"null", "null"), (b"7", "int")],
)
async def test_json_that_is_not_an_object_is_refused(
    backends: FakeBackends,
    body: bytes,
    kind: str,
) -> None:
    response = backends.make().answer(body)

    with pytest.raises(JsonError) as caught:
        _ = await response.to_array()

    assert str(caught.value) == (
        f'JSON content was expected to decode to an array, "{kind}" returned for "{URL}".'
    )


async def test_decoding_reports_an_unsuccessful_status_first(backends: FakeBackends) -> None:
    response = backends.make(500, JSON).answer(b'{"id": 7}')

    with pytest.raises(ServerError):
        _ = await response.to_array()

    assert await response.to_array(throw=False) == {"id": 7}


async def test_canceling_is_recorded_in_the_info() -> None:
    response = FakeBackend().response

    await response.cancel()

    assert response.get_info("canceled") is True
    assert response.get_info("error") == "Response has been canceled."


async def test_canceling_stops_the_producer_and_closes_the_body() -> None:
    backend = FakeBackend()

    await backend.response.cancel()

    assert backend.stopped
    assert not backend.response.get_body().is_readable()


async def test_a_canceled_response_cannot_be_read() -> None:
    backend = FakeBackend()
    backend.send(b"abc")
    await backend.response.cancel()

    with pytest.raises(TransportError) as caught:
        _ = await backend.response.get_content()

    assert str(caught.value) == "Response has been canceled."


async def test_canceling_tells_a_reader_waiting_for_the_body() -> None:
    backend = FakeBackend()
    errors: list[str] = []

    async def read() -> None:
        try:
            _ = await backend.response.get_content()
        except TransportError as error:
            errors.append(str(error))

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(read)
            await anyio.wait_all_tasks_blocked()
            await backend.response.cancel()

    assert errors == ["Response has been canceled."]


async def test_canceling_a_response_read_to_the_end_does_nothing(backends: FakeBackends) -> None:
    backend = backends.make()
    response = backend.answer(b"abc")
    _ = await response.get_content()

    await response.cancel()

    assert response.get_info("canceled") is False
    assert not backend.stopped
    assert await response.get_content() == b"abc"


async def test_leaving_a_block_over_a_status_nobody_looked_at_raises() -> None:
    backend = FakeBackend(404)

    with pytest.raises(ClientError) as caught:
        async with backend.response:
            pass

    assert caught.value.response is backend.response
    assert not backend.response.get_body().is_readable()


async def test_leaving_a_block_after_looking_at_the_status_raises_nothing() -> None:
    response = FakeBackend(404).response

    async with response:
        assert response.get_status_code() == 404


async def test_reading_the_content_counts_as_looking(backends: FakeBackends) -> None:
    response = backends.make(404).answer(b"gone")

    async with response:
        assert await response.get_content(throw=False) == b"gone"


async def test_leaving_a_block_over_a_success_closes_the_body_and_the_transfer() -> None:
    backend = FakeBackend()

    async with backend.response:
        pass

    assert not backend.response.get_body().is_readable()
    assert backend.stopped


async def test_an_exception_leaving_a_block_is_not_replaced() -> None:
    backend = FakeBackend(404)

    with pytest.raises(ValueError, match="raised in the block"):
        async with backend.response:
            raise ValueError("raised in the block")

    assert not backend.response.get_body().is_readable()


async def test_leaving_a_block_over_a_canceled_response_raises_nothing() -> None:
    response = FakeBackend(404).response

    async with response:
        await response.cancel()

    assert response.get_info("canceled") is True


async def test_a_run_opens_with_the_head_and_ends_with_the_last_chunk(
    backends: FakeBackends,
) -> None:
    response = backends.make().answer(b"abc", b"def")

    assert await run(HttpClientResponse.stream([response])) == ["first", b"abc", b"def", "last"]


async def test_each_chunk_comes_with_the_response_it_is_from(backends: FakeBackends) -> None:
    response = backends.make().answer()

    with anyio.fail_after(1):
        paired = [paired async for paired, _chunk in HttpClientResponse.stream([response])]

    assert paired == [response, response]


async def test_a_second_run_over_a_complete_response_says_so_again(
    backends: FakeBackends,
) -> None:
    response = backends.make().answer(b"abc")
    _ = await run(HttpClientResponse.stream([response]))

    assert await run(HttpClientResponse.stream([response])) == ["last"]


async def test_a_run_opens_without_a_head_somebody_looked_at(backends: FakeBackends) -> None:
    response = backends.make().answer(b"abc")
    _ = response.get_status_code()

    assert await run(HttpClientResponse.stream([response])) == [b"abc", "last"]


async def test_a_response_given_twice_is_read_once(backends: FakeBackends) -> None:
    response = backends.make().answer()

    assert await run(HttpClientResponse.stream([response, response])) == ["first", "last"]


async def test_a_run_waits_for_chunks_to_arrive(backends: FakeBackends) -> None:
    backend = backends.make()
    seen: list[str | bytes] = []

    async def read() -> None:
        seen.extend(await run(HttpClientResponse.stream([backend.response])))

    async with anyio.create_task_group() as group:
        _ = group.start_soon(read)
        await anyio.wait_all_tasks_blocked()
        _ = backend.answer(b"abc")

    assert seen == ["first", b"abc", "last"]


async def test_two_responses_interleave_in_the_order_their_chunks_arrive(
    backends: FakeBackends,
) -> None:
    first, second = backends.make(), backends.make()
    turns = [anyio.Event() for _ in range(4)]
    seen: list[tuple[ResponseInterface, bytes]] = []

    async def feed(backend: FakeBackend, mine: tuple[int, int], name: bytes) -> None:
        for number, turn in enumerate(mine, 1):
            await turns[turn].wait()
            backend.send(name + str(number).encode())
        backend.finish()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(feed, first, (0, 2), b"a")
            _ = group.start_soon(feed, second, (1, 3), b"b")
            turns[0].set()
            responses = [first.response, second.response]
            async for paired, chunk in HttpClientResponse.stream(responses):
                if describe(chunk) in {"first", "last"}:
                    continue
                seen.append((paired, chunk.get_content()))
                if len(seen) < len(turns):
                    turns[len(seen)].set()

    assert seen == [
        (first.response, b"a1"),
        (second.response, b"b1"),
        (first.response, b"a2"),
        (second.response, b"b2"),
    ]


async def test_a_quiet_run_says_so_and_a_later_run_carries_on(backends: FakeBackends) -> None:
    backend = backends.make()
    backend.send(b"<1>")
    _ = backend.response.get_status_code()

    assert await run(HttpClientResponse.stream([backend.response], 0.01)) == [b"<1>", "timeout"]

    _ = backend.answer(b"<2>")

    assert await run(HttpClientResponse.stream([backend.response], 0.01)) == [b"<2>", "last"]
    assert await backend.response.get_content() == b"<1><2>"


async def test_a_timeout_chunk_names_the_url_and_the_time_allowed(
    backends: FakeBackends,
) -> None:
    response = backends.make().response

    with anyio.fail_after(1):
        chunks = [chunk async for _paired, chunk in HttpClientResponse.stream([response], 0.01)]

    timeout = chunks[-1]
    assert isinstance(timeout, ErrorChunk)
    assert timeout.get_error() == f'Idle timeout reached for "{URL}".'
    assert timeout.timeout == 0.01


async def test_a_run_given_no_timeout_waits_as_long_as_its_slowest_response(
    backends: FakeBackends,
) -> None:
    responses = [backends.make(timeout=0.01).response, backends.make(timeout=0.02).response]

    with anyio.fail_after(1):
        chunks = [chunk async for _paired, chunk in HttpClientResponse.stream(responses)]

    timeouts = [chunk.timeout for chunk in chunks if isinstance(chunk, ErrorChunk)]
    assert timeouts == [0.02, 0.02]


async def test_data_a_run_took_is_gone_from_a_body_not_kept(backends: FakeBackends) -> None:
    response = backends.make(buffered=False).answer(b"abc")
    _ = await run(HttpClientResponse.stream([response]))

    with pytest.raises(TransportError, match="buffering is disabled"):
        _ = await response.get_content()


async def test_a_failure_ends_its_response_part_in_the_run(backends: FakeBackends) -> None:
    backend = backends.make()
    backend.send(b"abc")
    backend.transfer.fail(OSError("Connection reset by peer"))

    assert await run(HttpClientResponse.stream([backend.response])) == ["first", b"abc", "error"]


async def test_a_timeout_the_transfer_reports_ends_its_part_in_the_run(
    backends: FakeBackends,
) -> None:
    backend = backends.make()
    backend.transfer.push(backend.transfer.idle_chunk(URL, 0.1))
    backend.send(b"abc")

    assert await run(HttpClientResponse.stream([backend.response])) == ["first", "timeout"]


async def test_informational_statuses_reach_the_run(backends: FakeBackends) -> None:
    backend = backends.make()
    backend.transfer.push(InformationalChunk(103, {"link": ["</style.css>"]}))
    response = backend.answer()

    with anyio.fail_after(1):
        chunks = [chunk async for _paired, chunk in HttpClientResponse.stream([response])]

    assert chunks[1].get_informational_status() == (103, {"link": ["</style.css>"]})


async def test_a_canceled_response_leaves_a_run_saying_nothing() -> None:
    response = FakeBackend().response
    await response.cancel()

    assert await run(HttpClientResponse.stream([response])) == []


async def test_a_response_canceled_during_a_run_says_nothing_more() -> None:
    backend = FakeBackend()
    backend.send(b"abc")
    seen: list[str | bytes] = []

    with anyio.fail_after(1):
        async for paired, chunk in HttpClientResponse.stream([backend.response]):
            seen.append(describe(chunk))
            await paired.cancel()

    assert seen == ["first"]


def test_streaming_a_response_made_elsewhere_is_a_mistake() -> None:
    with pytest.raises(TypeError, match='"FakeResponse" given'):
        _ = HttpClientResponse.stream([FakeResponse()])
