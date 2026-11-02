from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_messenger import DelayStamp, Envelope, TransportMessageIdStamp

from tests.support.connections import connection_on
from tests.support.database_errors import refusal
from tests.support.faults import failing
from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger import TransportError
from xtr_orm_messenger.transport import OrmSender

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio


async def test_a_sent_envelope_is_stamped_with_its_row(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)

    sent = await OrmSender(connection, SERIALIZER, "orders").send(Envelope(OrderPlaced("o-1")))

    stamp = sent.last(TransportMessageIdStamp)
    assert stamp is not None
    stored = await connection.find(stamp.message_id)
    assert stored is not None
    assert stored.headers["type"] == "tests.orm_messenger.order_placed.v1"


async def test_a_delay_stamp_makes_the_message_due_later(
    engine: AsyncEngine, clock: MockClock
) -> None:
    connection = connection_on(engine, clock)

    _ = await OrmSender(connection, SERIALIZER, "orders").send(
        Envelope(OrderPlaced("o-1"), (DelayStamp(5000),))
    )

    assert await connection.get() is None
    clock.sleep(5)
    assert await connection.get() is not None


async def test_an_insert_the_database_refuses_is_a_transport_error(
    engine: AsyncEngine, clock: MockClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = connection_on(engine, clock)
    _ = failing(monkeypatch, "send", [refusal()])

    with pytest.raises(TransportError) as raised:
        _ = await OrmSender(connection, SERIALIZER, "orders").send(Envelope(OrderPlaced("o-1")))

    assert str(raised.value) == (
        'The "orders" transport could not send a message: permission denied.'
    )
