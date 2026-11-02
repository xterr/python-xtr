"""A cancelled send is neither a failure nor a reason to try another transport."""

from __future__ import annotations

import asyncio

import anyio
import pytest
from xtr_mime import Headers, Message, TextPart

from tests.support.scripted_transport import ScriptedTransport
from tests.support.stalling_transport import StallingTransport
from xtr_mailer.transport import FailoverTransport, RoundRobinTransport

pytestmark = pytest.mark.anyio


def _email() -> Message:
    headers = Headers()
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


async def _cancel_once_blocked(transport: RoundRobinTransport) -> list[BaseException]:
    """Send through ``transport``, cancel the send once it is blocked, and return what it raised."""
    raised: list[BaseException] = []

    async def send() -> None:
        try:
            _ = await transport.send(_email())
        except BaseException as error:
            raised.append(error)
            raise

    async with anyio.create_task_group() as group:
        _ = group.start_soon(send)
        await anyio.wait_all_tasks_blocked()
        group.cancel_scope.cancel()
    return raised


async def test_a_cancelled_send_reaches_the_caller_as_a_cancellation() -> None:
    transport = FailoverTransport([StallingTransport(), ScriptedTransport("t2")])

    raised = await _cancel_once_blocked(transport)

    assert len(raised) == 1
    assert isinstance(raised[0], anyio.get_cancelled_exc_class())


async def test_a_cancelled_send_is_not_tried_on_another_transport() -> None:
    t1, t2 = StallingTransport(), ScriptedTransport("t2")

    _ = await _cancel_once_blocked(FailoverTransport([t1, t2]))

    assert t2.received == []


async def test_a_cancelled_send_leaves_the_failover_on_its_transport() -> None:
    t1, t2 = StallingTransport(), ScriptedTransport("t2")
    transport = FailoverTransport([t1, t2])
    _ = await _cancel_once_blocked(transport)

    sent = await transport.send(_email())

    assert t1.sent == [sent]
    assert t2.received == []


@pytest.mark.usefixtures("first_turn")
async def test_a_cancelled_send_leaves_its_transport_alive_in_the_rotation() -> None:
    t1, t2 = StallingTransport(), ScriptedTransport("t2")
    transport = RoundRobinTransport([t1, t2])
    _ = await _cancel_once_blocked(transport)

    second = await transport.send(_email())
    third = await transport.send(_email())

    assert t2.sent == [second]
    assert t1.sent == [third]


async def test_an_asyncio_timeout_is_not_taken_for_a_failure() -> None:
    t1, t2 = StallingTransport(), ScriptedTransport("t2")
    transport = FailoverTransport([t1, t2])

    with pytest.raises(TimeoutError):
        _ = await asyncio.wait_for(transport.send(_email()), 0.05)
    sent = await transport.send(_email())

    assert t1.sent == [sent]
    assert t2.received == []
