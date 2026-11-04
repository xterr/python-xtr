from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_mime import Address, Headers, Message, RawMessage, TextPart
from xtr_mime.exception import LogicError as MimeLogicError

from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer import Envelope, LogicError, TransportError
from xtr_mailer.transport import FailoverTransport, RoundRobinTransport

if TYPE_CHECKING:
    from xtr_mailer import SentMessage

pytestmark = pytest.mark.anyio

_WIRE = b"Subject: Hi\r\n\r\nHello!\r\n"


def _email() -> Message:
    headers = Headers()
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


def _failure() -> TransportError:
    return TransportError("down")


class _Reading(ScriptedTransport):
    """Reads the bytes of each email it is handed, up to :attr:`chunks` chunks, before answering."""

    def __init__(self, name: str, chunks: int | None = None, *, fails: bool = False) -> None:
        super().__init__(name, [_failure()] if fails else [])
        self.chunks: int | None = chunks
        self.read: list[bytes] = []

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        chunks = message.to_iterable()
        if self.chunks is None:
            self.read.append(b"".join(chunks))
        else:
            self.read.append(b"".join(next(chunks) for _ in range(self.chunks)))
        return await super().send(message, envelope)


def _read_once() -> RawMessage:
    return RawMessage(iter([b"Subject: Hi\r\n", b"\r\n", b"Hello!\r\n"]))


def _envelope() -> Envelope:
    return Envelope(Address("from@example.com"), [Address("to@example.com")])


def test_it_takes_turns_only_when_a_transport_fails() -> None:
    assert isinstance(FailoverTransport([ScriptedTransport("t1")]), RoundRobinTransport)


def test_it_refuses_to_have_no_transport() -> None:
    with pytest.raises(TransportError) as caught:
        _ = FailoverTransport([])

    assert str(caught.value) == (
        '"xtr_mailer.transport.FailoverTransport" must have at least one transport configured.'
    )


def test_it_is_named_after_its_transports() -> None:
    transport = FailoverTransport(
        [ScriptedTransport("t1://local"), ScriptedTransport("t2://local")]
    )

    assert str(transport) == "failover(t1://local t2://local)"


async def test_the_first_transport_takes_every_email_while_it_works() -> None:
    t1, t2 = ScriptedTransport("t1"), ScriptedTransport("t2")
    transport = FailoverTransport([t1, t2])

    for _ in range(3):
        _ = await transport.send(_email())

    assert len(t1.sent) == 3
    assert t2.received == []


async def test_it_fails_once_every_transport_failed() -> None:
    t1, t2 = ScriptedTransport("t1", [_failure()]), ScriptedTransport("t2", [_failure()])
    transport = FailoverTransport([t1, t2])

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "All transports failed."
    assert [len(t1.received), len(t2.received)] == [1, 1]


async def test_the_next_transport_sends_a_read_once_body_the_failed_one_read_in_full() -> None:
    t1, t2 = _Reading("t1", fails=True), _Reading("t2")
    transport = FailoverTransport([t1, t2])

    sent = await transport.send(_read_once(), _envelope())

    assert t2.read == [_WIRE]
    assert sent is not None
    assert b"".join(sent.to_iterable()) == _WIRE


async def test_a_read_once_body_the_failed_transport_left_half_read_is_not_sent() -> None:
    t1, t2 = _Reading("t1", 1, fails=True), _Reading("t2")
    transport = FailoverTransport([t1, t2])

    with pytest.raises(MimeLogicError, match="generator is already closed"):
        _ = await transport.send(_read_once(), _envelope())

    assert t2.read == []
    assert t2.sent == []


async def test_the_next_transport_takes_over_from_a_failed_one() -> None:
    t1, t2 = ScriptedTransport("t1", [_failure()]), ScriptedTransport("t2")
    transport = FailoverTransport([t1, t2], clock=MockClock())

    for _ in range(3):
        _ = await transport.send(_email())

    assert len(t1.received) == 1
    assert len(t2.sent) == 3


async def test_a_dead_transport_takes_over_again_once_its_retry_period_is_over() -> None:
    clock = MockClock()
    t1 = ScriptedTransport("t1", [_failure()])
    t2 = ScriptedTransport("t2", [None, None, None, _failure()])
    transport = FailoverTransport([t1, t2], 6, clock=clock)
    _ = await transport.send(_email())  # t1 fails, t2
    for _ in range(3):  # t2, t2, then t2 fails and t1 is back after 12 seconds
        clock.sleep(4)
        _ = await transport.send(_email())

    clock.sleep(4)
    last = await transport.send(_email())

    assert len(t2.sent) == 3
    assert len(t1.sent) == 2
    assert t1.sent[-1] == last


async def test_it_fails_while_the_dead_transports_are_within_their_retry_period() -> None:
    clock = MockClock()
    t1 = ScriptedTransport("t1", [_failure(), _failure()])
    t2 = ScriptedTransport("t2", [None, None, _failure()])
    transport = FailoverTransport([t1, t2], 40, clock=clock)
    _ = await transport.send(_email())
    clock.sleep(4)
    _ = await transport.send(_email())
    clock.sleep(4)

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "All transports failed."
    assert len(t1.received) == 1


async def test_a_recovered_transport_takes_over_when_the_current_one_fails() -> None:
    clock = MockClock()
    t1 = ScriptedTransport("t1", [_failure()])
    t2 = ScriptedTransport("t2", [None, None, _failure()])
    transport = FailoverTransport([t1, t2], 1, clock=clock)
    _ = await transport.send(_email())
    clock.sleep(1)
    _ = await transport.send(_email())
    clock.sleep(1)

    last = await transport.send(_email())

    assert t1.sent == [last]


async def test_an_error_other_than_a_transport_failure_does_not_move_on() -> None:
    error = LogicError("broken email")
    t1, t2 = ScriptedTransport("t1", [error]), ScriptedTransport("t2")
    transport = FailoverTransport([t1, t2])

    with pytest.raises(LogicError) as caught:
        _ = await transport.send(_email())
    sent = await transport.send(_email())

    assert caught.value is error
    assert t1.sent == [sent]
    assert t2.received == []


async def test_a_send_tries_each_transport_once_when_each_try_outlasts_the_retry_period() -> None:
    clock = MockClock()
    t1, t2 = (
        ScriptedTransport(name, [_failure()] * 5, pause=lambda: clock.sleep_async(61))
        for name in ("t1", "t2")
    )
    transport = FailoverTransport([t1, t2], clock=clock)

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "All transports failed."
    assert [len(t1.received), len(t2.received)] == [1, 1]


async def test_a_send_tries_each_transport_once_without_a_retry_period() -> None:
    clock = MockClock()
    t1, t2 = (
        ScriptedTransport(name, [_failure()] * 5, pause=lambda: clock.sleep_async(1))
        for name in ("t1", "t2")
    )
    transport = FailoverTransport([t1, t2], 0, clock=clock)

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "All transports failed."
    assert [len(t1.received), len(t2.received)] == [1, 1]
