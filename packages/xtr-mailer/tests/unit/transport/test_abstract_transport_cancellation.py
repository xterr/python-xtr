"""A send of :class:`AbstractTransport` cancelled mid-way: no wait, no outcome event."""

from __future__ import annotations

import asyncio

import anyio
import pytest
from xtr_clock import MockClock
from xtr_mime import Address, RawMessage

from tests.support.recorded_events import recording_dispatcher
from tests.support.stalling_transport import StallingTransport
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent

pytestmark = pytest.mark.anyio

_MESSAGE = RawMessage(b"")


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


async def test_a_send_cancelled_mid_way_waits_for_nothing_after_its_turn() -> None:
    clock = MockClock()
    transport = StallingTransport(clock=clock).set_max_per_second(1 / 10)
    transport.stalled = True
    _ = await transport.send(_MESSAGE, _envelope())
    transport.stalled = False
    start = clock.now().timestamp()

    with pytest.raises(TimeoutError):
        _ = await asyncio.wait_for(transport.send(_MESSAGE, _envelope()), 0.05)

    assert clock.now().timestamp() - start == pytest.approx(10)


async def test_a_cancelled_send_counts_towards_the_pace() -> None:
    clock = MockClock()
    transport = StallingTransport(clock=clock).set_max_per_second(1 / 10)
    with anyio.move_on_after(0.05):
        _ = await transport.send(_MESSAGE, _envelope())
    start = clock.now().timestamp()

    _ = await transport.send(_MESSAGE, _envelope())

    assert clock.now().timestamp() - start == pytest.approx(10)


async def test_a_cancelled_send_announces_neither_outcome() -> None:
    dispatcher, recorded = recording_dispatcher()
    transport = StallingTransport(dispatcher)

    with anyio.move_on_after(0.05):
        _ = await transport.send(_MESSAGE, _envelope())

    assert [type(event) for event in recorded] == [MessageEvent]
