from __future__ import annotations

import anyio
import pytest

from xtr_http_client.chunk import DataChunk, ErrorChunk, InformationalChunk, LastChunk
from xtr_http_client.exception import TransportError, TransportTimeoutError
from xtr_http_client.internal.transfer import Transfer
from xtr_http_client.internal.transfer_source import TransferSource

pytestmark = pytest.mark.anyio

URL = "https://example.com/"


def source_over(transfer: Transfer) -> TransferSource:
    return TransferSource(transfer, {"url": URL})


def test_it_is_its_own_iterator() -> None:
    source = source_over(Transfer(timeout=60.0))

    assert aiter(source) is source


async def test_it_hands_over_the_body_a_piece_at_a_time() -> None:
    transfer = Transfer(timeout=60.0)
    for chunk in (DataChunk(0, b"abc"), DataChunk(3, b"de"), LastChunk(5)):
        transfer.push(chunk)
    source = source_over(transfer)

    assert [piece async for piece in source] == [b"abc", b"de"]


async def test_it_passes_over_chunks_that_carry_no_body() -> None:
    transfer = Transfer(timeout=60.0)
    for chunk in (InformationalChunk(103, {}), DataChunk(0, b""), DataChunk(0, b"abc")):
        transfer.push(chunk)

    assert await anext(source_over(transfer)) == b"abc"


async def test_it_waits_for_the_next_piece() -> None:
    transfer = Transfer(timeout=60.0)
    source = source_over(transfer)
    pieces: list[bytes] = []

    async def read() -> None:
        pieces.append(await anext(source))

    with anyio.fail_after(1):
        async with anyio.create_task_group() as group:
            _ = group.start_soon(read)
            await anyio.wait_all_tasks_blocked()
            transfer.push(DataChunk(0, b"abc"))

    assert pieces == [b"abc"]


async def test_a_failed_transfer_raises_on_every_read() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.fail(OSError("Connection reset by peer"))
    source = source_over(transfer)

    with pytest.raises(TransportError, match="Connection reset by peer"):
        _ = await anext(source)
    with pytest.raises(TransportError, match="Connection reset by peer"):
        _ = await anext(source)


async def test_going_quiet_for_the_idle_timeout_raises_and_reading_carries_on() -> None:
    transfer = Transfer(timeout=0.01)
    source = source_over(transfer)

    with anyio.fail_after(1), pytest.raises(TransportTimeoutError) as caught:
        _ = await anext(source)
    transfer.push(DataChunk(0, b"abc"))

    assert str(caught.value) == f'Idle timeout reached for "{URL}".'
    assert await anext(source) == b"abc"


async def test_a_timeout_the_transfer_reports_raises_too() -> None:
    transfer = Transfer(timeout=60.0)
    transfer.push(ErrorChunk(0, f'Idle timeout reached for "{URL}".'))
    transfer.push(DataChunk(0, b"abc"))
    source = source_over(transfer)

    with pytest.raises(TransportTimeoutError):
        _ = await anext(source)
    assert await anext(source) == b"abc"


async def test_closing_it_lets_go_of_the_transfer() -> None:
    transfer = Transfer(timeout=60.0)

    await source_over(transfer).aclose()

    assert transfer.canceled
