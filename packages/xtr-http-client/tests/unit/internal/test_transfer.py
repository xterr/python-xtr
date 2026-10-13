from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest

from xtr_http_client.chunk import DataChunk, ErrorChunk, InformationalChunk, LastChunk
from xtr_http_client.exception import TransportError
from xtr_http_client.internal.transfer import Transfer

if TYPE_CHECKING:
    from xtr_http_client_contracts import ChunkInterface

pytestmark = pytest.mark.anyio


def test_a_chunk_is_taken_once() -> None:
    transfer = Transfer(timeout=60.0)
    chunk = DataChunk(0, b"abc")
    transfer.push(chunk)

    assert transfer.take_ready() is chunk
    assert transfer.take_ready() is None


def test_chunks_come_out_in_the_order_they_were_pushed() -> None:
    transfer = Transfer(timeout=60.0)
    informational = InformationalChunk(103, {"link": ["</style.css>"]})
    data = DataChunk(0, b"abc")
    transfer.push(informational)
    transfer.push(data)

    assert [transfer.take_ready(), transfer.take_ready()] == [informational, data]


def test_the_offset_follows_the_body_pushed() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(DataChunk(0, b"abc"))
    transfer.push(InformationalChunk(100, {}))
    transfer.push(DataChunk(3, b"de"))

    assert transfer.offset == 5


def test_it_keeps_the_idle_timeout_it_was_given() -> None:
    assert Transfer(timeout=2.5).timeout == 2.5


async def test_a_reader_waits_for_the_next_chunk() -> None:
    transfer = Transfer(timeout=60.0)
    taken: list[ChunkInterface] = []

    async def read() -> None:
        taken.append(await transfer.next_chunk())

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(read)
            await anyio.wait_all_tasks_blocked()
            assert taken == []
            transfer.push(DataChunk(0, b"abc"))

    assert [chunk.get_content() for chunk in taken] == [b"abc"]


async def test_a_ready_chunk_is_handed_over_without_waiting() -> None:
    transfer = Transfer(timeout=60.0)
    chunk = DataChunk(0, b"abc")
    transfer.push(chunk)

    with anyio.fail_after(1):
        assert await transfer.next_chunk() is chunk


def test_a_finished_transfer_keeps_handing_out_its_last_chunk() -> None:
    transfer = Transfer(timeout=60.0)
    last = LastChunk(3)
    transfer.push(last)

    assert transfer.take_ready() is last
    assert transfer.take_ready() is last
    assert transfer.finished


def test_a_transfer_is_not_finished_until_its_last_chunk_is_taken() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(LastChunk(0))

    assert not transfer.finished


def test_nothing_is_pushed_after_the_last_chunk() -> None:
    transfer = Transfer(timeout=60.0)
    last = LastChunk(0)
    transfer.push(last)
    transfer.push(DataChunk(0, b"late"))

    assert [transfer.take_ready(), transfer.take_ready()] == [last, last]


def test_failing_ends_the_transfer_with_what_broke_it() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(DataChunk(0, b"abc"))
    transfer.fail(OSError("Connection reset by peer"))
    _ = transfer.take_ready()

    failure = transfer.take_ready()

    assert failure is not None
    assert failure.get_error() == "Connection reset by peer"
    assert failure.get_offset() == 3
    assert transfer.take_ready() is failure
    assert transfer.error == "Connection reset by peer"


def test_a_failure_raises_from_the_chunk_it_ends_with() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.fail(OSError("Connection reset by peer"))
    failure = transfer.take_ready()
    assert failure is not None

    with pytest.raises(TransportError, match="Connection reset by peer"):
        _ = failure.is_last()


def test_a_timeout_chunk_does_not_end_the_transfer() -> None:
    transfer = Transfer(timeout=60.0)
    timeout = ErrorChunk(0, 'Idle timeout reached for "https://example.com/".')
    data = DataChunk(0, b"abc")
    transfer.push(timeout)
    transfer.push(data)

    assert [transfer.take_ready(), transfer.take_ready()] == [timeout, data]
    assert not transfer.finished
    assert transfer.error is None


def test_canceling_stops_the_producer_and_drops_what_nobody_took() -> None:
    transfer = Transfer(timeout=60.0)
    stopped: list[bool] = []
    transfer.on_cancel = lambda: stopped.append(True)
    transfer.push(DataChunk(0, b"abc"))

    transfer.cancel()
    end = transfer.take_ready()

    assert stopped == [True]
    assert end is not None
    assert end.get_error() == "Response has been canceled."
    assert transfer.canceled
    assert transfer.finished


def test_a_canceled_transfer_is_not_a_failed_one() -> None:
    transfer = Transfer(timeout=60.0)

    transfer.cancel()

    assert transfer.error is None


def test_canceling_works_without_a_producer_to_stop() -> None:
    transfer = Transfer(timeout=60.0)

    transfer.cancel()

    assert transfer.canceled


def test_canceling_twice_stops_the_producer_once() -> None:
    transfer = Transfer(timeout=60.0)
    stopped: list[bool] = []
    transfer.on_cancel = lambda: stopped.append(True)

    transfer.cancel()
    transfer.cancel()

    assert stopped == [True]


def test_canceling_a_finished_transfer_does_nothing() -> None:
    transfer = Transfer(timeout=60.0)
    stopped: list[bool] = []
    transfer.on_cancel = lambda: stopped.append(True)
    last = LastChunk(0)
    transfer.push(last)
    _ = transfer.take_ready()

    transfer.cancel()

    assert stopped == []
    assert not transfer.canceled
    assert transfer.take_ready() is last


def test_canceling_after_the_producer_ended_leaves_it_alone() -> None:
    transfer = Transfer(timeout=60.0)
    stopped: list[bool] = []
    transfer.on_cancel = lambda: stopped.append(True)
    transfer.push(LastChunk(0))

    transfer.cancel()

    assert stopped == []
    assert transfer.canceled


async def test_canceling_wakes_a_waiting_reader() -> None:
    transfer = Transfer(timeout=60.0)
    taken: list[ChunkInterface] = []

    async def read() -> None:
        taken.append(await transfer.next_chunk())

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(read)
            await anyio.wait_all_tasks_blocked()
            transfer.cancel()

    assert [chunk.get_error() for chunk in taken] == ["Response has been canceled."]


async def test_waiting_on_several_transfers_ends_when_any_of_them_gets_a_chunk() -> None:
    quiet = Transfer(timeout=60.0)
    busy = Transfer(timeout=60.0)
    woken: list[bool] = []

    async def wait() -> None:
        await Transfer.wait_any([quiet, busy])
        woken.append(busy.ready)

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(wait)
            await anyio.wait_all_tasks_blocked()
            busy.push(DataChunk(0, b"abc"))

    assert woken == [True]
    assert quiet._listeners == busy._listeners == set()


async def test_waiting_lasts_until_a_chunk_arrives() -> None:
    with anyio.move_on_after(0.01) as waited:
        await Transfer.wait_any([Transfer(timeout=60.0)])

    assert waited.cancelled_caught


async def test_waiting_ends_at_once_when_a_chunk_is_already_there() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(DataChunk(0, b"abc"))

    with anyio.fail_after(1):
        await Transfer.wait_any([transfer])


async def test_waiting_ends_at_once_on_a_finished_transfer() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(LastChunk(0))
    _ = transfer.take_ready()

    with anyio.fail_after(1):
        await Transfer.wait_any([transfer])


def test_it_is_ready_while_a_take_would_hand_something_over() -> None:
    transfer = Transfer(timeout=60.0)
    assert not transfer.ready

    transfer.push(LastChunk(0))
    assert transfer.ready

    _ = transfer.take_ready()
    assert transfer.ready


def test_a_push_wakes_a_listener_only_while_it_listens() -> None:
    transfer = Transfer(timeout=60.0)
    during, after = anyio.Event(), anyio.Event()

    with transfer.waking(during):
        transfer.push(DataChunk(0, b"abc"))
    with transfer.waking(after):
        pass
    transfer.push(DataChunk(3, b"def"))

    assert during.is_set()
    assert not after.is_set()


def test_an_idle_chunk_says_where_the_body_had_got_to() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(DataChunk(0, b"abc"))

    chunk = transfer.idle_chunk("https://example.com/", 0.5)

    assert chunk.is_timeout()
    assert chunk.get_error() == 'Idle timeout reached for "https://example.com/".'
    assert chunk.get_offset() == 3
    assert chunk.timeout == 0.5
