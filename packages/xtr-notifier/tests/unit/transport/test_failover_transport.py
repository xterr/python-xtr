from __future__ import annotations

import pytest
from xtr_clock import MockClock
from xtr_http_client import MockResponse

from tests.support.dummy_message import DummyMessage
from tests.support.fake_transport import FakeTransport
from xtr_notifier.exception import LogicError, NotifierRuntimeError, TransportError
from xtr_notifier.transport import FailoverTransport, RoundRobinTransport

pytestmark = pytest.mark.anyio


def _down() -> TransportError:
    return TransportError("down", MockResponse())


def test_it_refuses_to_be_built_without_transports() -> None:
    with pytest.raises(LogicError) as caught:
        _ = FailoverTransport([])

    assert str(caught.value) == '"FailoverTransport" must have at least one transport configured.'


def test_it_is_a_round_robin_named_with_the_failover_symbol() -> None:
    transport = FailoverTransport([FakeTransport("t1"), FakeTransport("t2")])

    assert isinstance(transport, RoundRobinTransport)
    assert str(transport) == "t1://local || t2://local"


async def test_it_refuses_a_message_no_transport_supports() -> None:
    transport = FailoverTransport([FakeTransport(supports=False), FakeTransport(supports=False)])

    with pytest.raises(LogicError) as caught:
        _ = await transport.send(DummyMessage())

    assert str(caught.value) == (
        'None of the configured Transports of "FailoverTransport" supports the given message.'
    )


async def test_it_keeps_sending_through_the_first_transport_while_it_works() -> None:
    t1, t2 = FakeTransport("t1"), FakeTransport("t2")
    transport = FailoverTransport([t1, t2])

    for _ in range(3):
        _ = await transport.send(DummyMessage())

    assert len(t1.sent) == 3
    assert t2.sent == []


async def test_it_fails_when_every_transport_fails() -> None:
    t1 = FakeTransport("t1", outcomes=[_down()])
    t2 = FakeTransport("t2", outcomes=[_down()])

    with pytest.raises(NotifierRuntimeError) as caught:
        _ = await FailoverTransport([t1, t2]).send(DummyMessage())

    assert str(caught.value) == "All transports failed."
    assert len(t1.sent) == 1
    assert len(t2.sent) == 1


async def test_it_moves_to_the_next_transport_when_one_fails() -> None:
    t1 = FakeTransport("t1", outcomes=[_down()])
    t2 = FakeTransport("t2")

    sent = await FailoverTransport([t1, t2]).send(DummyMessage())

    assert sent.transport == "t2"
    assert len(t1.sent) == 1


async def test_a_failure_other_than_a_transport_error_is_not_failed_over() -> None:
    t1 = FakeTransport("t1", outcomes=[ValueError("bug")])
    t2 = FakeTransport("t2")

    with pytest.raises(ValueError, match="bug"):
        _ = await FailoverTransport([t1, t2]).send(DummyMessage())

    assert t2.sent == []


async def test_it_fails_while_every_transport_is_still_resting() -> None:
    clock = MockClock()
    t1 = FakeTransport("t1", outcomes=[_down()])
    t2 = FakeTransport("t2", outcomes=[None, None, _down()])
    transport = FailoverTransport([t1, t2], 40, clock)

    _ = await transport.send(DummyMessage())
    clock.sleep(4)
    _ = await transport.send(DummyMessage())
    clock.sleep(4)

    with pytest.raises(NotifierRuntimeError, match=r"^All transports failed\.$"):
        _ = await transport.send(DummyMessage())

    assert len(t1.sent) == 1
    assert len(t2.sent) == 3


async def test_a_dead_transport_is_tried_again_once_its_rest_is_over() -> None:
    clock = MockClock()
    t1 = FakeTransport("t1", outcomes=[_down()])
    t2 = FakeTransport("t2", outcomes=[None, _down()])
    transport = FailoverTransport([t1, t2], 1, clock)

    _ = await transport.send(DummyMessage())
    clock.sleep(2)
    sent = await transport.send(DummyMessage())

    assert sent.transport == "t1"
    assert len(t1.sent) == 2
    assert len(t2.sent) == 2
