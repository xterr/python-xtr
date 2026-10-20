from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock
from xtr_http_client import MockResponse

from tests.support.dummy_message import DummyMessage
from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import LogicError, NotifierRuntimeError, TransportError
from xtr_notifier.transport import RoundRobinTransport, TransportInterface

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface

pytestmark = pytest.mark.anyio


def _down() -> TransportError:
    return TransportError("down", MockResponse())


def _first(stop: int) -> int:
    return stop - stop


def _last(stop: int) -> int:
    return stop - 1


@pytest.fixture
def start_at_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the random starting point the first transport."""
    monkeypatch.setattr(random, "randrange", _first)


def test_it_refuses_to_be_built_without_transports() -> None:
    with pytest.raises(LogicError) as caught:
        _ = RoundRobinTransport([])

    assert str(caught.value) == '"RoundRobinTransport" must have at least one transport configured.'


def test_it_is_named_after_its_transports() -> None:
    transport = RoundRobinTransport([FakeTransport("t1"), FakeTransport("t2")])

    assert isinstance(transport, TransportInterface)
    assert str(transport) == "t1://local && t2://local"


def test_it_supports_a_message_one_transport_supports() -> None:
    message = DummyMessage()

    assert RoundRobinTransport([FakeTransport(supports=False), FakeTransport()]).supports(message)
    assert not RoundRobinTransport([FakeTransport(supports=False)]).supports(message)


async def test_it_refuses_a_message_no_transport_supports() -> None:
    transport = RoundRobinTransport([FakeTransport(supports=False)])

    with pytest.raises(LogicError) as caught:
        _ = await transport.send(DummyMessage())

    assert str(caught.value) == (
        'None of the configured Transports of "RoundRobinTransport" supports the given message.'
    )


@pytest.mark.usefixtures("start_at_first")
async def test_it_takes_turns_between_its_transports() -> None:
    transport = RoundRobinTransport([FakeTransport("t1"), FakeTransport("t2")])

    names = [(await transport.send(DummyMessage())).transport for _ in range(4)]

    assert names == ["t1", "t2", "t1", "t2"]


async def test_it_starts_at_a_random_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "randrange", _last)
    transport = RoundRobinTransport([FakeTransport("t1"), FakeTransport("t2"), FakeTransport("t3")])

    sent = await transport.send(DummyMessage())

    assert sent.transport == "t3"


@pytest.mark.usefixtures("start_at_first")
async def test_it_skips_a_transport_that_does_not_support_the_message() -> None:
    t1 = FakeTransport("t1", supports=False)
    transport = RoundRobinTransport([t1, FakeTransport("t2")])

    names = [(await transport.send(DummyMessage())).transport for _ in range(2)]

    assert names == ["t2", "t2"]
    assert t1.sent == []


@pytest.mark.usefixtures("start_at_first")
async def test_a_dead_transport_is_skipped_until_its_rest_is_over() -> None:
    clock = MockClock()
    t1 = FakeTransport("t1", outcomes=[_down()])
    transport = RoundRobinTransport([t1, FakeTransport("t2")], 60, clock)

    first = await transport.send(DummyMessage())
    second = await transport.send(DummyMessage())
    clock.sleep(61)
    third = await transport.send(DummyMessage())

    assert [first.transport, second.transport, third.transport] == ["t2", "t2", "t1"]


@pytest.mark.usefixtures("start_at_first")
async def test_it_fails_when_every_transport_is_dead() -> None:
    transport = RoundRobinTransport(
        [FakeTransport("t1", outcomes=[_down()]), FakeTransport("t2", outcomes=[_down()])]
    )

    with pytest.raises(NotifierRuntimeError, match=r"^All transports failed\.$"):
        _ = await transport.send(DummyMessage())


@pytest.mark.usefixtures("start_at_first")
async def test_it_stops_looking_when_the_only_live_transports_do_not_support_the_message() -> None:
    def chat_only(message: MessageInterface) -> bool:
        return message.subject == "chat"

    t1 = FakeTransport("t1", outcomes=[_down()])
    t2 = FakeTransport("t2", supports=chat_only)
    transport = RoundRobinTransport([t1, t2])
    with pytest.raises(NotifierRuntimeError):
        _ = await transport.send(DummyMessage(subject="sms"))
    _ = await transport.send(DummyMessage(subject="chat"))

    # The turn now starts at the dead transport, with only an unsupporting one beside it.
    with pytest.raises(NotifierRuntimeError, match=r"^All transports failed\.$"):
        _ = await transport.send(DummyMessage(subject="sms"))

    assert [message.subject for message in t2.sent] == ["chat"]
