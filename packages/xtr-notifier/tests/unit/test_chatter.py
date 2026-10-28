from __future__ import annotations

import pytest

from tests.support.dummy_message import DummyMessage
from tests.support.fake_transport import FakeTransport
from tests.support.recorded_events import recording_dispatcher
from tests.support.recording_message_bus import RecordingMessageBus
from xtr_notifier import Chatter, ChatterInterface
from xtr_notifier.event import MessageEvent

pytestmark = pytest.mark.anyio


def test_it_is_a_chatter_called_chat() -> None:
    chatter = Chatter(FakeTransport())

    assert isinstance(chatter, ChatterInterface)
    assert str(chatter) == "chat"


def test_it_supports_what_its_transport_supports() -> None:
    assert Chatter(FakeTransport()).supports(DummyMessage())
    assert not Chatter(FakeTransport(supports=False)).supports(DummyMessage())


async def test_it_sends_through_its_transport_without_a_bus() -> None:
    transport = FakeTransport("any")
    message = DummyMessage()

    sent = await Chatter(transport).send(message)

    assert sent is not None
    assert sent.original_message is message
    assert transport.sent == [message]


async def test_it_queues_on_the_bus_instead_of_sending() -> None:
    transport = FakeTransport()
    bus = RecordingMessageBus()
    message = DummyMessage()

    sent = await Chatter(transport, bus).send(message)

    assert sent is None
    assert bus.messages == [message]
    assert transport.sent == []


async def test_it_announces_a_queued_message() -> None:
    dispatcher, recorded = recording_dispatcher()
    message = DummyMessage()

    _ = await Chatter(FakeTransport(), RecordingMessageBus(), dispatcher).send(message)

    assert len(recorded) == 1
    event = recorded[0]
    assert isinstance(event, MessageEvent)
    assert event.message is message
    assert event.queued
