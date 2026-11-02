from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from xtr_messenger import (
    Envelope,
    ReceivedStamp,
    TransportMessageIdStamp,
)

from tests.support.connections import connection_on
from tests.support.database_errors import deadlock, lost_connection, refusal
from tests.support.faults import failing
from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger import TransportError
from xtr_orm_messenger.transport import (
    MAX_RETRIES,
    RECONNECT_TIMEOUT,
    Connection,
    OrmReceivedStamp,
    OrmReceiver,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio


def _receiver(connection: Connection, clock: MockClock) -> OrmReceiver:
    return OrmReceiver(connection, SERIALIZER, "orders", clock)


async def _send(connection: Connection, envelope: Envelope, delay_ms: int = 0) -> str:
    encoded = SERIALIZER.encode(envelope)
    return await connection.send(encoded.body, encoded.headers, delay_ms)


async def test_a_message_arrives_stamped_with_its_transport_and_its_row(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await _send(connection, Envelope(OrderPlaced("o-1")))

    received = await anext(_receiver(connection, clock).get())

    assert received.message == OrderPlaced("o-1")
    assert received.last(ReceivedStamp) == ReceivedStamp("orders")
    assert received.last(OrmReceivedStamp) == OrmReceivedStamp(message_id)
    assert received.all(TransportMessageIdStamp) == (TransportMessageIdStamp(message_id),)


async def test_the_id_an_earlier_transport_gave_is_replaced_by_the_rows(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    message_id = await _send(
        connection, Envelope(OrderPlaced("o-1"), (TransportMessageIdStamp("elsewhere"),))
    )

    received = await anext(_receiver(connection, clock).get())

    assert received.all(TransportMessageIdStamp) == (TransportMessageIdStamp(message_id),)


async def test_a_worker_waits_until_a_message_falls_due(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("later")), delay_ms=3000)

    received = await anext(_receiver(connection, clock).get())

    assert received.message == OrderPlaced("later")
    assert clock.now().isoformat() == "2026-01-01T00:00:03+00:00"


async def test_a_message_that_does_not_decode_is_rejected_and_the_next_one_received(
    engine: AsyncEngine, clock: MockClock, caplog: pytest.LogCaptureFixture
) -> None:
    connection = connection_on(engine, clock)
    broken = await connection.send('{"secret": "s3cr3t"}', {"type": "tests.nobody.declares.this"})
    _ = await _send(connection, Envelope(OrderPlaced("o-2")))

    with caplog.at_level(logging.WARNING, logger="messenger"):
        received = await anext(_receiver(connection, clock).get())

    assert received.message == OrderPlaced("o-2")
    assert await connection.find(broken) is None
    assert f"rejecting message {broken} of the 'orders' transport" in caplog.text
    assert "s3cr3t" not in caplog.text


@pytest.mark.parametrize("settle", ["ack", "reject"])
async def test_settling_deletes_the_row(engine: AsyncEngine, clock: MockClock, settle: str) -> None:
    connection = connection_on(engine, clock)
    message_id = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())

    await (receiver.ack if settle == "ack" else receiver.reject)(received)

    assert await connection.find(message_id) is None


async def test_an_envelope_from_another_transport_cannot_be_settled_here(
    engine: AsyncEngine, clock: MockClock
) -> None:
    receiver = _receiver(connection_on(engine, clock), clock)

    with pytest.raises(TransportError) as refusal_raised:
        await receiver.ack(Envelope(OrderPlaced("o-1")))

    assert "carries no OrmReceivedStamp" in str(refusal_raised.value)


async def test_a_poll_sits_out_conflicts_short_of_the_limit(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    calls = failing(monkeypatch, "get", [deadlock()] * (MAX_RETRIES - 1))

    received = await anext(_receiver(connection, clock).get())

    assert received.message == OrderPlaced("o-1")
    assert calls[0] == MAX_RETRIES


async def test_a_poll_gives_up_after_too_many_conflicts_in_a_row(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = failing(monkeypatch, "get", [deadlock()] * MAX_RETRIES)

    with pytest.raises(TransportError) as raised:
        _ = await anext(_receiver(connection, clock).get())

    assert raised.value.operation == "get messages"


async def test_a_successful_poll_forgets_the_conflicts_before_it(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    _ = await _send(connection, Envelope(OrderPlaced("o-2")))
    receiver = _receiver(connection, clock)
    _ = failing(monkeypatch, "get", [deadlock()] * (MAX_RETRIES - 1))
    stream = receiver.get()
    _ = await anext(stream)
    _ = failing(monkeypatch, "get", [deadlock()] * (MAX_RETRIES - 1))

    received = await anext(stream)

    assert received.message == OrderPlaced("o-2")


async def test_a_poll_the_database_refuses_for_another_reason_fails_at_once(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    calls = failing(monkeypatch, "get", [refusal()])

    with pytest.raises(TransportError) as raised:
        _ = await anext(_receiver(connection, clock).get())

    assert calls[0] == 1
    assert "permission denied" in str(raised.value)


async def test_a_settle_tries_again_after_a_conflict_with_a_growing_pause(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    message_id = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    before = clock.now()
    calls = failing(monkeypatch, "ack", [deadlock()] * MAX_RETRIES)

    await receiver.ack(received)

    waited = (clock.now() - before).total_seconds()
    assert calls[0] == MAX_RETRIES + 1
    assert 0.7 * 0.9 <= waited <= 0.7 * 1.1
    assert await connection.find(message_id) is None


async def test_a_settle_gives_up_after_too_many_conflicts(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    _ = failing(monkeypatch, "reject", [deadlock()] * (MAX_RETRIES + 1))

    with pytest.raises(TransportError) as raised:
        await receiver.reject(received)

    assert raised.value.operation.startswith("reject message")


async def test_a_settle_lost_to_a_database_restart_is_replayed_once_it_answers(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    message_id = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    calls = failing(monkeypatch, "ack", [lost_connection()])
    pings = [False, True]

    async def answers(_self: Connection) -> bool:
        return pings.pop(0)

    monkeypatch.setattr(Connection, "ping", answers)

    await receiver.ack(received)

    assert calls[0] == 2
    assert pings == []
    assert await connection.find(message_id) is None


async def test_a_settle_gives_up_when_the_database_does_not_come_back(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    before = clock.now()
    _ = failing(monkeypatch, "ack", [lost_connection()])

    async def silent(_self: Connection) -> bool:
        return False

    monkeypatch.setattr(Connection, "ping", silent)

    with pytest.raises(TransportError):
        await receiver.ack(received)

    assert (clock.now() - before).total_seconds() == RECONNECT_TIMEOUT


async def test_a_settle_is_replayed_only_once(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    calls = failing(monkeypatch, "ack", [lost_connection(), lost_connection()])

    async def answers(_self: Connection) -> bool:
        return True

    monkeypatch.setattr(Connection, "ping", answers)

    with pytest.raises(TransportError):
        await receiver.ack(received)

    assert calls[0] == 2


async def test_a_settle_the_database_refuses_for_another_reason_fails_at_once(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = await _send(connection, Envelope(OrderPlaced("o-1")))
    receiver = _receiver(connection, clock)
    received = await anext(receiver.get())
    calls = failing(monkeypatch, "ack", [refusal()])

    with pytest.raises(TransportError):
        await receiver.ack(received)

    assert calls[0] == 1
