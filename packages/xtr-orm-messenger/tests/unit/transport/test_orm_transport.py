from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_messenger import Envelope, ReceivedStamp, TransportInterface, TransportMessageIdStamp

from tests.support.connections import connection_on
from tests.support.database_errors import refusal
from tests.support.faults import failing
from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger import TransportError
from xtr_orm_messenger.transport import OrmOptions, OrmReceivedStamp, OrmTransport

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio


def _transport(
    engine: AsyncEngine, clock: MockClock, options: OrmOptions | None = None
) -> OrmTransport:
    return OrmTransport(
        connection_on(engine, clock, options), SERIALIZER, name="orders", clock=clock
    )


async def test_it_is_a_whole_transport(engine: AsyncEngine, clock: MockClock) -> None:
    transport = _transport(engine, clock)

    assert isinstance(transport, TransportInterface)
    assert transport.name == "orders"
    assert transport.connection.options == OrmOptions()


async def test_what_is_sent_is_received_and_acknowledged(
    engine: AsyncEngine, clock: MockClock
) -> None:
    transport = _transport(engine, clock)

    sent = await transport.send(Envelope(OrderPlaced("o-1")))
    received = await anext(transport.get())
    await transport.ack(received)

    assert received.message == OrderPlaced("o-1")
    assert received.last(ReceivedStamp) == ReceivedStamp("orders")
    assert sent.last(TransportMessageIdStamp) == received.last(TransportMessageIdStamp)
    assert await transport.count() == 0


async def test_a_rejected_message_is_gone(engine: AsyncEngine, clock: MockClock) -> None:
    transport = _transport(engine, clock, OrmOptions(redeliver_timeout=1))
    _ = await transport.send(Envelope(OrderPlaced("o-1")))

    await transport.reject(await anext(transport.get()))
    clock.sleep(5)

    assert await transport.count() == 0


async def test_a_message_kept_alive_is_not_handed_out_again(
    engine: AsyncEngine, clock: MockClock
) -> None:
    transport = _transport(engine, clock, OrmOptions(redeliver_timeout=60))
    _ = await transport.send(Envelope(OrderPlaced("o-1")))
    received = await anext(transport.get())

    clock.sleep(50)
    await transport.keepalive(received, seconds=30)
    clock.sleep(50)

    assert await transport.count() == 0


async def test_keepalive_refuses_to_wait_longer_than_the_redeliver_timeout(
    engine: AsyncEngine, clock: MockClock
) -> None:
    transport = _transport(engine, clock, OrmOptions(redeliver_timeout=60))
    received = Envelope(OrderPlaced("o-1"), (OrmReceivedStamp("1"),))

    with pytest.raises(TransportError) as raised:
        await transport.keepalive(received, seconds=61)

    assert "61 seconds is longer than its redeliver_timeout of 60" in str(raised.value)


async def test_keepalive_refuses_an_envelope_from_another_transport(
    engine: AsyncEngine, clock: MockClock
) -> None:
    with pytest.raises(TransportError) as raised:
        await _transport(engine, clock).keepalive(Envelope(OrderPlaced("o-1")))

    assert "carries no OrmReceivedStamp" in str(raised.value)


async def test_find_and_all_hand_back_envelopes(engine: AsyncEngine, clock: MockClock) -> None:
    transport = _transport(engine, clock)
    sent = await transport.send(Envelope(OrderPlaced("o-1")))
    stamp = sent.last(TransportMessageIdStamp)
    assert stamp is not None

    found = await transport.find(stamp.message_id)
    listed = [envelope.message async for envelope in transport.all()]

    assert found is not None
    assert found.message == OrderPlaced("o-1")
    assert found.last(OrmReceivedStamp) == OrmReceivedStamp(stamp.message_id)
    assert listed == [OrderPlaced("o-1")]
    assert await transport.find("999") is None


async def test_setup_creates_the_table_ahead_of_time(engine: AsyncEngine, clock: MockClock) -> None:
    transport = _transport(engine, clock, OrmOptions(auto_setup=False))

    await transport.setup()

    assert await transport.count() == 0


async def test_a_keepalive_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport(engine, clock)
    _ = failing(monkeypatch, "keepalive", [refusal()])
    received = Envelope(OrderPlaced("o-1"), (OrmReceivedStamp("1"),))

    with pytest.raises(TransportError) as raised:
        await transport.keepalive(received)

    assert raised.value.operation == "keep a message alive"


async def test_a_lookup_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport(engine, clock)
    _ = failing(monkeypatch, "find", [refusal()])

    with pytest.raises(TransportError) as raised:
        _ = await transport.find("1")

    assert raised.value.operation == "find a message"


async def test_a_count_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport(engine, clock)
    _ = failing(monkeypatch, "count", [refusal()])

    with pytest.raises(TransportError) as raised:
        _ = await transport.count()

    assert raised.value.operation == "count messages"


async def test_a_setup_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport(engine, clock)
    _ = failing(monkeypatch, "setup", [refusal()])

    with pytest.raises(TransportError) as raised:
        await transport.setup()

    assert raised.value.operation == "create its table"


async def test_a_listing_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport(engine, clock)
    _ = failing(monkeypatch, "_rows", [refusal()])

    with pytest.raises(TransportError) as raised:
        _ = [envelope async for envelope in transport.all()]

    assert raised.value.operation == "list messages"


async def test_closing_a_transport_that_never_listened_does_nothing(
    engine: AsyncEngine, clock: MockClock
) -> None:
    await _transport(engine, clock).close()
