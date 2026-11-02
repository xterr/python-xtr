"""The pace :meth:`AbstractTransport.set_max_per_second` sets holds for concurrent senders."""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING

import anyio
import pytest
from anyio.lowlevel import checkpoint
from typing_extensions import override
from xtr_mime import Address, Headers, Message, RawMessage, TextPart

from tests.support.fake_transport import FakeTransport
from tests.support.virtual_clock import VirtualClock
from xtr_mailer import Envelope
from xtr_mailer.transport import Transports

if TYPE_CHECKING:
    from xtr_mailer import SentMessage

pytestmark = pytest.mark.anyio

_MESSAGE = RawMessage(b"")


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


class _TimedTransport(FakeTransport):
    """Notes when each send was handed over, in seconds since the clock's start.

    The sends whose position is in :attr:`failing` fail once noted.
    """

    def __init__(self, clock: VirtualClock) -> None:
        super().__init__(clock=clock)
        self.start: float = clock.now().timestamp()
        self.times: list[float] = []
        self.failing: set[int] = set()

    @override
    async def _do_send(self, message: SentMessage) -> None:
        self.times.append(self._clock.now().timestamp() - self.start)
        if len(self.times) - 1 in self.failing:
            raise ValueError
        await super()._do_send(message)


async def _send_concurrently(clock: VirtualClock, transport: _TimedTransport, count: int) -> int:
    failures = 0

    async def send() -> None:
        nonlocal failures
        try:
            _ = await transport.send(_MESSAGE, _envelope())
        except ValueError:
            failures += 1

    async with anyio.create_task_group() as group:
        for _ in range(count):
            _ = group.start_soon(send)
        while await clock.advance():
            pass
    return failures


async def test_concurrent_sends_are_spaced_by_the_max_per_second() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(2)

    _ = await _send_concurrently(clock, transport, 5)

    assert transport.times == pytest.approx([0, 0.5, 1, 1.5, 2])


async def test_concurrent_sends_go_at_once_without_a_rate() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock)

    _ = await _send_concurrently(clock, transport, 5)

    assert transport.times == [0, 0, 0, 0, 0]


async def test_failures_in_the_middle_keep_the_spacing() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(2)
    transport.failing = {1, 3}

    failures = await _send_concurrently(clock, transport, 5)

    assert failures == 2
    assert transport.times == pytest.approx([0, 0.5, 1, 1.5, 2])


async def test_a_send_cancelled_while_waiting_keeps_the_others_spaced() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(2)
    cancelled = anyio.CancelScope()

    async def send_cancellable() -> None:
        with cancelled:
            _ = await transport.send(_MESSAGE, _envelope())

    async with anyio.create_task_group() as group:
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        _ = group.start_soon(send_cancellable)
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        await anyio.wait_all_tasks_blocked()
        cancelled.cancel()
        while await clock.advance():
            pass

    assert transport.times == pytest.approx([0, 1, 1.5])


async def test_a_cancelled_burst_gives_its_slots_back() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(1)
    burst = anyio.CancelScope()

    async def send_burst() -> None:
        with burst:
            async with anyio.create_task_group() as senders:
                for _ in range(100):
                    _ = senders.start_soon(transport.send, _MESSAGE, _envelope())

    async def cancel_burst() -> None:
        await clock.sleep_async(5.5)
        burst.cancel()

    async def send_after_the_burst() -> None:
        await clock.sleep_async(6)
        _ = await transport.send(_MESSAGE, _envelope())

    async with anyio.create_task_group() as group:
        _ = group.start_soon(send_burst)
        _ = group.start_soon(cancel_burst)
        _ = group.start_soon(send_after_the_burst)
        while await clock.advance():
            pass

    assert transport.times == pytest.approx([0, 1, 2, 3, 4, 5, 6])


async def test_the_last_waiting_send_cancelled_gives_its_slot_to_the_next() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(2)
    last = anyio.CancelScope()

    async def send_last() -> None:
        with last:
            _ = await transport.send(_MESSAGE, _envelope())

    async def cancel_last_then_send() -> None:
        await clock.sleep_async(0.25)
        last.cancel()
        await checkpoint()  # the cancelled send unwinds before this one takes a slot
        _ = await transport.send(_MESSAGE, _envelope())

    async with anyio.create_task_group() as group:
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        _ = group.start_soon(send_last)
        await anyio.wait_all_tasks_blocked()
        _ = group.start_soon(cancel_last_then_send)
        while await clock.advance():
            pass

    assert transport.times == pytest.approx([0, 0.5, 1])


async def test_cancelled_waits_and_new_sends_never_start_closer_than_the_pace() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(2)
    scopes = [anyio.CancelScope() for _ in range(6)]

    async def send_in(scope: anyio.CancelScope) -> None:
        with scope:
            _ = await transport.send(_MESSAGE, _envelope())

    async def cancel_and_send(at: float, cancelled: list[int], sends: int) -> None:
        await clock.sleep_async(at)
        for index in cancelled:
            scopes[index].cancel()
        await checkpoint()
        async with anyio.create_task_group() as senders:
            for _ in range(sends):
                _ = senders.start_soon(transport.send, _MESSAGE, _envelope())

    async with anyio.create_task_group() as group:
        for scope in scopes:
            _ = group.start_soon(send_in, scope)
        await anyio.wait_all_tasks_blocked()
        _ = group.start_soon(cancel_and_send, 0.75, [5, 4], 2)
        _ = group.start_soon(cancel_and_send, 1.2, [3, 2], 1)
        while await clock.advance():
            pass

    starts = sorted(transport.times)
    assert len(starts) == 6
    assert all(later - earlier >= 0.5 - 1e-9 for earlier, later in pairwise(starts))


async def test_a_wait_cancelled_after_the_pace_was_set_afresh_gives_nothing_back() -> None:
    clock = VirtualClock()
    transport = _TimedTransport(clock).set_max_per_second(1)
    waiting = anyio.CancelScope()

    async def send_waiting() -> None:
        with waiting:
            _ = await transport.send(_MESSAGE, _envelope())

    async def reset_then_cancel() -> None:
        await clock.sleep_async(0.25)
        _ = transport.set_max_per_second(1)
        _ = await transport.send(_MESSAGE, _envelope())
        waiting.cancel()
        await checkpoint()
        _ = await transport.send(_MESSAGE, _envelope())

    async with anyio.create_task_group() as group:
        _ = group.start_soon(transport.send, _MESSAGE, _envelope())
        _ = group.start_soon(send_waiting)
        await anyio.wait_all_tasks_blocked()
        _ = group.start_soon(reset_then_cancel)
        while await clock.advance():
            pass

    assert transport.times == pytest.approx([0, 0.25, 1.25])


async def test_concurrent_sends_through_transports_are_paced() -> None:
    clock = VirtualClock()
    throttled = _TimedTransport(clock).set_max_per_second(2)
    transports = Transports({"main": FakeTransport(), "bulk": throttled})

    def routed() -> Message:
        headers = (
            Headers()
            .add_text_header("X-Transport", "bulk")
            .add_mailbox_list_header("From", ["fabien@example.com"])
            .add_mailbox_list_header("To", ["helene@example.com"])
        )
        return Message(headers, TextPart("..."))

    async with anyio.create_task_group() as group:
        for _ in range(3):
            _ = group.start_soon(transports.send, routed(), _envelope())
        while await clock.advance():
            pass

    assert throttled.times == pytest.approx([0, 0.5, 1])
