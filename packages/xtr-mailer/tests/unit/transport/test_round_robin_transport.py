from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_logging_contracts import EXCEPTION_KEY, AbstractLogger, Level
from xtr_mime import Headers, Message, TextPart

from tests.support.fake_transport import FakeTransport
from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer import Envelope, LogicError, SentMessage, TransportError
from xtr_mailer.transport import (
    FailoverTransport,
    RoundRobinTransport,
    StoppableTransportInterface,
    TransportInterface,
)

if TYPE_CHECKING:
    from xtr_logging_contracts import Context, LevelLike
    from xtr_mime import RawMessage

pytestmark = pytest.mark.anyio


def _email() -> Message:
    headers = Headers()
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


def _failure(debug: str = "") -> TransportError:
    error = TransportError("down")
    error.append_debug(debug)
    return error


class _RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.records: list[tuple[LevelLike, str, Context | None]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.records.append((level, message, context))


class _Tampering(ScriptedTransport):
    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        assert isinstance(message, Message)
        _ = message.get_headers().add_text_header("X-Transport-1", "value")
        return await super().send(message, envelope)


class _Connection(ScriptedTransport):
    stops: int = 0

    async def stop(self) -> None:
        self.stops += 1


def test_it_is_a_stoppable_transport() -> None:
    transport = RoundRobinTransport([ScriptedTransport("t1")])

    assert isinstance(transport, TransportInterface)
    assert isinstance(transport, StoppableTransportInterface)


def test_it_refuses_to_have_no_transport() -> None:
    with pytest.raises(TransportError) as caught:
        _ = RoundRobinTransport([])

    assert str(caught.value) == (
        '"xtr_mailer.transport.RoundRobinTransport" must have at least one transport configured.'
    )


def test_it_is_named_after_its_transports() -> None:
    transport = RoundRobinTransport(
        [ScriptedTransport("t1://local"), ScriptedTransport("t2://local")]
    )

    assert str(transport) == "roundrobin(t1://local t2://local)"


async def test_the_first_turn_goes_to_a_random_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    uppers: list[int] = []

    def last(upper: int) -> int:
        uppers.append(upper)
        return upper - 1

    monkeypatch.setattr("xtr_mailer.transport.round_robin_transport.randbelow", last)
    t1, t2, t3 = ScriptedTransport("t1"), ScriptedTransport("t2"), ScriptedTransport("t3")

    _ = await RoundRobinTransport([t1, t2, t3]).send(_email())

    assert uppers == [3]
    assert [len(t1.sent), len(t2.sent), len(t3.sent)] == [0, 0, 1]


@pytest.mark.usefixtures("first_turn")
async def test_the_transports_take_turns() -> None:
    t1, t2 = ScriptedTransport("t1"), ScriptedTransport("t2")
    transport = RoundRobinTransport([t1, t2])

    first = await transport.send(_email())
    second = await transport.send(_email())
    third = await transport.send(_email())

    assert t1.sent == [first, third]
    assert t2.sent == [second]


@pytest.mark.usefixtures("first_turn")
async def test_it_fails_once_every_transport_failed() -> None:
    t1, t2 = ScriptedTransport("t1", [_failure()]), ScriptedTransport("t2", [_failure()])
    transport = RoundRobinTransport([t1, t2])

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "All transports failed."
    assert [len(t1.received), len(t2.received)] == [1, 1]


@pytest.mark.usefixtures("first_turn")
async def test_it_finds_no_transport_while_every_one_is_dead() -> None:
    t1, t2 = ScriptedTransport("t1", [_failure()]), ScriptedTransport("t2", [_failure()])
    transport = RoundRobinTransport([t1, t2], clock=MockClock())
    with pytest.raises(TransportError):
        _ = await transport.send(_email())

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert str(caught.value) == "No transports found."
    assert [len(t1.received), len(t2.received)] == [1, 1]


@pytest.mark.usefixtures("first_turn")
async def test_a_failed_transport_is_skipped_afterwards() -> None:
    t1, t2 = ScriptedTransport("t1", [_failure()]), ScriptedTransport("t2")
    transport = RoundRobinTransport([t1, t2], clock=MockClock())

    for _ in range(3):
        _ = await transport.send(_email())

    assert len(t1.received) == 1
    assert len(t2.sent) == 3


@pytest.mark.usefixtures("first_turn")
async def test_a_dead_transport_stays_skipped_within_its_retry_period() -> None:
    t1, t2 = ScriptedTransport("t1"), ScriptedTransport("t2", [_failure()])
    transport = RoundRobinTransport([t1, t2], 60, clock=MockClock())

    for _ in range(4):
        _ = await transport.send(_email())

    assert len(t1.sent) == 4
    assert len(t2.received) == 1


@pytest.mark.usefixtures("first_turn")
async def test_a_dead_transport_is_tried_again_after_its_retry_period() -> None:
    clock = MockClock()
    t1, t2 = ScriptedTransport("t1"), ScriptedTransport("t2", [_failure()])
    transport = RoundRobinTransport([t1, t2], 3, clock=clock)
    _ = await transport.send(_email())  # t1
    _ = await transport.send(_email())  # t2 fails, t1
    clock.sleep(5)

    third = await transport.send(_email())
    fourth = await transport.send(_email())

    assert t2.sent == [third]
    assert t1.sent[-1] == fourth
    assert len(t1.sent) == 3


@pytest.mark.usefixtures("first_turn")
async def test_each_transport_is_handed_its_own_copy_of_the_email() -> None:
    t1, t2 = _Tampering("t1", [_failure()]), ScriptedTransport("t2")
    transport = RoundRobinTransport([t1, t2])
    email = _email()
    _ = email.get_headers().add_text_header("X-Shared", "value")

    sent = await transport.send(email)

    assert email.get_headers().get_header_body("X-Shared") == "value"
    assert not email.get_headers().has("X-Transport-1")
    assert sent is not None
    original = sent.get_original_message()
    assert isinstance(original, Message)
    assert not original.get_headers().has("X-Transport-1")


@pytest.mark.usefixtures("first_turn")
async def test_a_failure_is_logged() -> None:
    error = _failure()
    t1, t2 = ScriptedTransport("t1"), ScriptedTransport("t2", [error])
    logger = _RecordingLogger()
    transport = RoundRobinTransport([t1, t2], logger=logger)

    _ = await transport.send(_email())
    _ = await transport.send(_email())

    assert logger.records == [
        (Level.ERROR, 'Transport "{transport}" failed.', {"transport": "t2", EXCEPTION_KEY: error})
    ]
    assert len(t1.sent) == 2


async def test_the_error_carries_what_each_failed_transport_said() -> None:
    t1 = ScriptedTransport("t1", [_failure("Debug message 1")])
    t2 = ScriptedTransport("t2", [_failure("Debug message 2")])
    transport = RoundRobinTransport([t1, t2])

    with pytest.raises(TransportError) as caught:
        _ = await transport.send(_email())

    assert sorted(caught.value.debug.splitlines()) == [
        'Transport "t1": Debug message 1',
        'Transport "t2": Debug message 2',
    ]
    assert caught.value.debug.endswith("\n")
    assert str(caught.value) == "All transports failed."


@pytest.mark.usefixtures("first_turn")
async def test_an_error_other_than_a_transport_failure_reaches_the_caller_at_once() -> None:
    error = LogicError("broken email")
    t1, t2 = ScriptedTransport("t1", [error]), ScriptedTransport("t2")
    transport = RoundRobinTransport([t1, t2])

    with pytest.raises(LogicError) as caught:
        _ = await transport.send(_email())
    _ = await transport.send(_email())
    _ = await transport.send(_email())

    assert caught.value is error
    assert [len(t1.received), len(t2.received)] == [2, 1]


async def test_stop_stops_the_transports_that_hold_a_connection() -> None:
    connection, nested = _Connection("smtp://a"), _Connection("smtp://b")
    transport = RoundRobinTransport(
        [connection, FailoverTransport([nested]), FakeTransport(), ScriptedTransport("t")]
    )

    await transport.stop()

    assert (connection.stops, nested.stops) == (1, 1)
