from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

import pytest
from xtr_http_message_contracts import StreamInterface

from xtr_http_client.internal.response_body import ResponseBody

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.anyio


@final
class ScriptedTransfer:
    """Hands a body its pieces one pull at a time, the way a transfer would."""

    def __init__(self, pieces: Sequence[bytes], buffered: bool = True) -> None:
        self.remaining = list(pieces)
        self.pulls = 0
        self.body = ResponseBody(self.pull, buffered=buffered)

    async def pull(self) -> bool:
        self.pulls += 1
        if not self.remaining:
            self.body.finish()
            return False
        self.body.append(self.remaining.pop(0))
        return True


@final
class FailingTransfer:
    """A transfer that breaks on the first step."""

    def __init__(self) -> None:
        self.body = ResponseBody(self.pull, buffered=True)

    async def pull(self) -> bool:
        raise OSError("Connection reset by peer")


def test_it_is_a_message_body() -> None:
    body: StreamInterface = ScriptedTransfer([]).body
    assert isinstance(body, StreamInterface)


async def test_it_reads_what_the_transfer_has_produced_so_far() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body

    assert await body.read(64) == b"abc"
    assert await body.read(64) == b"def"
    assert await body.read(64) == b""


async def test_it_reads_no_more_than_it_was_asked_for() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body

    assert await body.read(2) == b"ab"
    assert await body.read(2) == b"c"
    assert await body.read(2) == b"de"
    assert body.tell() == 5


async def test_it_pulls_nothing_when_nothing_is_asked_for() -> None:
    transfer = ScriptedTransfer([b"abc"])

    assert await transfer.body.read(0) == b""
    assert transfer.pulls == 0


async def test_the_contents_are_the_whole_body() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body

    assert await body.get_contents() == b"abcdef"
    assert body.received == 6
    assert body.complete is True


async def test_a_kept_body_reads_the_same_the_second_time() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body

    assert await body.get_contents() == b"abcdef"
    assert await body.get_contents() == b"abcdef"


async def test_a_body_that_is_not_kept_is_gone_after_one_read() -> None:
    body = ScriptedTransfer([b"abc", b"def"], buffered=False).body

    assert await body.get_contents() == b"abcdef"
    assert await body.get_contents() == b""


async def test_a_body_that_is_not_kept_drops_what_was_read() -> None:
    body = ScriptedTransfer([b"abc", b"def"], buffered=False).body

    _ = await body.read(64)
    _ = await body.read(64)

    assert body._window == b""


async def test_an_empty_body_can_always_be_read_again() -> None:
    body = ScriptedTransfer([], buffered=False).body

    assert await body.get_contents() == b""
    assert body.buffered is True
    assert await body.get_contents() == b""


async def test_a_body_still_arriving_cannot_be_rewound() -> None:
    body = ScriptedTransfer([b"abc"]).body

    assert body.is_seekable() is False
    with pytest.raises(RuntimeError, match="cannot be rewound"):
        await body.rewind()


async def test_a_body_that_is_not_kept_cannot_be_rewound_once_complete() -> None:
    body = ScriptedTransfer([b"abc"], buffered=False).body
    _ = await body.get_contents()

    assert body.is_seekable() is False


async def test_a_kept_and_complete_body_seeks_from_anywhere() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body
    _ = await body.get_contents()

    await body.seek(3)
    assert await body.read(64) == b"def"
    await body.seek(-3, os.SEEK_END)
    assert await body.read(64) == b"def"
    await body.seek(0)
    await body.seek(4, os.SEEK_CUR)
    assert await body.read(64) == b"ef"


async def test_it_refuses_a_position_before_the_first_byte() -> None:
    body = ScriptedTransfer([b"abc"]).body
    _ = await body.get_contents()

    with pytest.raises(RuntimeError, match="before the body"):
        await body.seek(-1)


async def test_it_refuses_a_whence_it_does_not_know() -> None:
    body = ScriptedTransfer([b"abc"]).body
    _ = await body.get_contents()

    with pytest.raises(ValueError, match="whence"):
        await body.seek(0, 99)


async def test_reading_past_the_end_of_a_kept_body_gives_nothing() -> None:
    body = ScriptedTransfer([b"abc"]).body
    _ = await body.get_contents()

    await body.seek(10)

    assert await body.read(64) == b""
    assert body.eof() is True


async def test_nothing_can_be_written_to_it() -> None:
    body = ScriptedTransfer([b"abc"]).body

    assert body.is_writable() is False
    with pytest.raises(RuntimeError, match="cannot be written"):
        _ = await body.write(b"abc")


async def test_a_closed_body_cannot_be_read() -> None:
    body = ScriptedTransfer([b"abc"]).body

    await body.close()

    assert body.is_readable() is False
    assert body.is_seekable() is False
    with pytest.raises(RuntimeError, match="closed"):
        _ = await body.read(64)


async def test_it_knows_its_size_once_it_is_complete_and_kept() -> None:
    body = ScriptedTransfer([b"abc", b"def"]).body

    assert body.get_size() is None
    _ = await body.get_contents()
    assert body.get_size() == 6


async def test_a_body_that_is_not_kept_never_knows_its_size() -> None:
    body = ScriptedTransfer([b"abc"], buffered=False).body
    _ = await body.get_contents()

    assert body.get_size() is None


async def test_the_cursor_is_at_the_end_only_once_the_body_is_complete() -> None:
    body = ScriptedTransfer([b"abc"]).body

    assert body.tell() == 0
    assert body.eof() is False
    assert await body.read(64) == b"abc"
    assert body.eof() is False
    assert await body.read(64) == b""
    assert body.eof() is True
    assert body.tell() == 3


async def test_what_broke_the_transfer_reaches_the_reader_unchanged() -> None:
    body = FailingTransfer().body

    with pytest.raises(OSError, match="Connection reset by peer"):
        _ = await body.read(64)


def test_it_wraps_no_file_object() -> None:
    assert ScriptedTransfer([]).body.detach() is None


def test_it_describes_itself() -> None:
    body = ScriptedTransfer([b"abc"]).body

    assert body.get_metadata() == {"mode": "rb", "seekable": False, "eof": False}
    assert body.get_metadata("mode") == "rb"
    assert body.get_metadata("nothing-of-the-sort") is None
