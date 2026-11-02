"""Sends overlapping in time through one round-robin or failover transport."""

from __future__ import annotations

import anyio
import pytest
from xtr_mime import Headers, Message, TextPart

from tests.support.scripted_transport import ScriptedTransport
from tests.support.virtual_clock import VirtualClock
from xtr_mailer import TransportError
from xtr_mailer.transport import FailoverTransport, RoundRobinTransport

pytestmark = pytest.mark.anyio


def _email() -> Message:
    headers = Headers()
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


def _slow(clock: VirtualClock, name: str, *outcomes: Exception | None) -> ScriptedTransport:
    """A transport taking five seconds of ``clock`` to answer each send."""
    return ScriptedTransport(name, outcomes, pause=lambda: clock.sleep_async(5))


async def _send_together(
    transport: RoundRobinTransport, clock: VirtualClock, count: int
) -> list[Exception]:
    """Start ``count`` sends at once, move ``clock`` on until every one is over, return errors."""
    errors: list[Exception] = []

    async def send() -> None:
        try:
            _ = await transport.send(_email())
        except Exception as error:  # noqa: BLE001 -- collected for the test to assert on
            errors.append(error)

    async with anyio.create_task_group() as group:
        for _ in range(count):
            _ = group.start_soon(send)
        while await clock.advance():
            pass
    return errors


@pytest.mark.usefixtures("first_turn")
async def test_overlapping_sends_each_take_their_own_turn() -> None:
    clock = VirtualClock()
    start = clock.now().timestamp()
    transports = [_slow(clock, "t1"), _slow(clock, "t2"), _slow(clock, "t3")]

    errors = await _send_together(RoundRobinTransport(transports, clock=clock), clock, 3)

    assert errors == []
    assert [len(transport.sent) for transport in transports] == [1, 1, 1]
    assert clock.now().timestamp() - start == 5


async def test_overlapping_sends_failing_on_one_transport_all_fail_over() -> None:
    clock = VirtualClock()
    t1, t2 = _slow(clock, "t1", TransportError("down"), TransportError("down")), _slow(clock, "t2")
    transport = FailoverTransport([t1, t2], clock=clock)

    overlapping = await _send_together(transport, clock, 2)
    alone = await _send_together(transport, clock, 1)

    assert overlapping + alone == []
    assert len(t1.received) == 2
    assert len(t2.sent) == 3


async def test_a_transport_failing_under_overlapping_sends_rests_on_the_clock() -> None:
    clock = VirtualClock()
    t1 = _slow(clock, "t1", TransportError("down"), TransportError("down"))
    t2 = _slow(clock, "t2", None, None, TransportError("down"))
    transport = FailoverTransport([t1, t2], 20, clock=clock)
    _ = await _send_together(transport, clock, 2)  # both fail on t1 at 5 s, t2 sends at 10 s
    clock.sleep(4)

    errors = await _send_together(transport, clock, 1)  # t2 fails at 19 s; t1 rests until 25 s

    assert [str(error) for error in errors] == ["All transports failed."]
    assert len(t1.received) == 2
