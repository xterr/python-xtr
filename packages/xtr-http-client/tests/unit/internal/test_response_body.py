from __future__ import annotations

import os
from typing import TYPE_CHECKING, Self, final

import pytest
from xtr_http_message_contracts import StreamInterface

from xtr_http_client.internal.response_body import _SPILL_AT, ResponseBody

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

MEBIBYTE = 1024 * 1024


async def arriving(*pieces: bytes) -> AsyncIterator[bytes]:
    for piece in pieces:
        yield piece


async def breaking() -> AsyncIterator[bytes]:
    yield b"abc"
    raise OSError("Connection reset by peer")


@final
class SilentTransfer:
    """A transfer with nothing of its own to let go of."""

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        raise StopAsyncIteration


@final
class Bodies:
    """Makes bodies and lets go of every one of them when the test is over.

    A kept body holds a temporary file, so a test that leaves one behind
    leaves the file behind too; closing them all here is what the response
    that owns a body does.
    """

    def __init__(self) -> None:
        self._made: list[ResponseBody] = []

    def over(self, source: AsyncIterator[bytes], buffered: bool = True) -> ResponseBody:
        body = ResponseBody(source, buffered=buffered)
        self._made.append(body)
        return body

    async def close(self) -> None:
        for body in self._made:
            await body.close()


@pytest.fixture
async def bodies() -> AsyncIterator[Bodies]:
    made = Bodies()
    yield made
    await made.close()


def test_it_is_a_message_body() -> None:
    body: StreamInterface = ResponseBody(arriving(), buffered=True)
    assert isinstance(body, StreamInterface)


async def test_it_reads_what_the_transfer_has_produced_so_far(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))

    assert await body.read(64) == b"abc"
    assert await body.read(64) == b"def"
    assert await body.read(64) == b""


async def test_it_reads_no_more_than_it_was_asked_for(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))

    assert await body.read(2) == b"ab"
    assert await body.read(2) == b"c"
    assert await body.read(2) == b"de"
    assert body.tell() == 5


async def test_it_takes_nothing_from_the_transfer_when_nothing_is_asked_for(
    bodies: Bodies,
) -> None:
    body = bodies.over(arriving(b"abc"))

    assert await body.read(0) == b""
    assert body.received == 0
    assert body.complete is False


async def test_the_contents_are_the_whole_body(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))

    assert await body.get_contents() == b"abcdef"
    assert body.received == 6
    assert body.complete is True


async def test_a_kept_body_reads_the_same_the_second_time(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))

    assert await body.get_contents() == b"abcdef"
    assert await body.get_contents() == b"abcdef"


async def test_a_kept_body_is_held_in_a_message_stream(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))
    _ = await body.get_contents()

    assert isinstance(body._kept, StreamInterface)


async def test_a_body_that_is_not_kept_is_gone_after_one_read(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"), buffered=False)

    assert await body.get_contents() == b"abcdef"
    assert await body.get_contents() == b""


async def test_a_body_that_is_not_kept_keeps_no_history(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"), buffered=False)

    _ = await body.get_contents()

    assert body._pending == b""
    assert body._kept is None


async def test_an_empty_body_can_always_be_read_again(bodies: Bodies) -> None:
    body = bodies.over(arriving(), buffered=False)

    assert await body.get_contents() == b""
    assert body.buffered is True
    assert await body.get_contents() == b""
    assert body.get_size() == 0


async def test_an_empty_body_rewinds_to_where_it_already_was(bodies: Bodies) -> None:
    body = bodies.over(arriving(), buffered=False)
    _ = await body.get_contents()

    await body.rewind()

    assert body.tell() == 0


async def test_a_body_still_arriving_cannot_be_rewound(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))

    assert body.is_seekable() is False
    with pytest.raises(RuntimeError, match="cannot be rewound"):
        await body.rewind()


async def test_a_body_that_is_not_kept_cannot_be_rewound_once_complete(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"), buffered=False)
    _ = await body.get_contents()

    assert body.is_seekable() is False


async def test_a_kept_and_complete_body_seeks_from_anywhere(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))
    _ = await body.get_contents()

    await body.seek(3)
    assert await body.read(64) == b"def"
    await body.seek(-3, os.SEEK_END)
    assert await body.read(64) == b"def"
    await body.seek(0)
    await body.seek(4, os.SEEK_CUR)
    assert await body.read(64) == b"ef"


async def test_it_refuses_a_position_before_the_first_byte(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))
    _ = await body.get_contents()

    with pytest.raises(RuntimeError, match="before the body"):
        await body.seek(-1)


async def test_it_refuses_a_whence_it_does_not_know(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))
    _ = await body.get_contents()

    with pytest.raises(ValueError, match="whence"):
        await body.seek(0, 99)


async def test_reading_past_the_end_of_a_kept_body_gives_nothing(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))
    _ = await body.get_contents()

    await body.seek(10)

    assert await body.read(64) == b""
    assert body.eof() is True


async def test_a_kept_body_past_the_spill_point_still_reads_again(bodies: Bodies) -> None:
    pieces = [bytes([index]) * MEBIBYTE for index in range(1, 4)]
    body = bodies.over(arriving(*pieces))
    whole = b"".join(pieces)

    assert len(whole) > _SPILL_AT
    assert await body.get_contents() == whole
    assert body.get_size() == len(whole)
    assert await body.get_contents() == whole


async def test_nothing_can_be_written_to_it(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))

    assert body.is_writable() is False
    with pytest.raises(RuntimeError, match="cannot be written"):
        _ = await body.write(b"abc")


async def test_a_closed_body_cannot_be_read(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))

    await body.close()

    assert body.is_readable() is False
    assert body.is_seekable() is False
    with pytest.raises(RuntimeError, match="closed"):
        _ = await body.read(64)


async def test_closing_the_body_closes_the_transfer_behind_it(bodies: Bodies) -> None:
    transfer = arriving(b"abc", b"def")
    body = bodies.over(transfer)
    _ = await body.read(64)

    await body.close()

    with pytest.raises(StopAsyncIteration):
        _ = await anext(transfer)


async def test_closing_the_body_lets_go_of_what_it_was_kept_in(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))
    _ = await body.get_contents()
    kept = body._kept
    assert kept is not None

    await body.close()

    assert kept.detach() is None


async def test_closing_a_body_whose_transfer_has_nothing_to_close_is_enough(
    bodies: Bodies,
) -> None:
    body = bodies.over(SilentTransfer())

    await body.close()

    assert body.is_readable() is False


async def test_it_knows_its_size_once_it_is_complete_and_kept(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc", b"def"))

    assert body.get_size() is None
    _ = await body.get_contents()
    assert body.get_size() == 6


async def test_a_body_that_is_not_kept_never_knows_its_size(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"), buffered=False)
    _ = await body.get_contents()

    assert body.get_size() is None


async def test_the_cursor_is_at_the_end_only_once_the_body_is_complete(bodies: Bodies) -> None:
    body = bodies.over(arriving(b"abc"))

    assert body.tell() == 0
    assert body.eof() is False
    assert await body.read(64) == b"abc"
    assert body.eof() is False
    assert await body.read(64) == b""
    assert body.eof() is True
    assert body.tell() == 3


async def test_what_broke_the_transfer_reaches_the_reader_unchanged(bodies: Bodies) -> None:
    body = bodies.over(breaking())

    assert await body.read(64) == b"abc"
    with pytest.raises(OSError, match="Connection reset by peer"):
        _ = await body.read(64)


def test_it_wraps_no_file_object() -> None:
    assert ResponseBody(arriving(), buffered=True).detach() is None


def test_it_describes_itself() -> None:
    body = ResponseBody(arriving(b"abc"), buffered=True)

    assert body.get_metadata() == {"mode": "rb", "seekable": False, "eof": False}
    assert body.get_metadata("mode") == "rb"
    assert body.get_metadata("nothing-of-the-sort") is None
