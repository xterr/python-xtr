from __future__ import annotations

import pytest

from tests.support.dummy_message import DummyMessage
from tests.support.recorded_events import recording_dispatcher
from xtr_notifier.event import MessageEvent, SentMessageEvent
from xtr_notifier.message import NullMessage
from xtr_notifier.transport import NullTransport, TransportInterface

pytestmark = pytest.mark.anyio


def test_it_is_called_null() -> None:
    assert str(NullTransport()) == "null"


def test_it_supports_every_message() -> None:
    transport = NullTransport()

    assert isinstance(transport, TransportInterface)
    assert transport.supports(DummyMessage())


async def test_it_sends_nowhere_and_reports_a_null_message() -> None:
    message = DummyMessage()

    sent = await NullTransport().send(message)

    assert isinstance(sent.original_message, NullMessage)
    assert sent.original_message.message is message
    assert sent.transport == "null"


async def test_it_announces_the_message_and_the_send() -> None:
    dispatcher, recorded = recording_dispatcher()

    sent = await NullTransport(dispatcher).send(DummyMessage())

    assert [type(event) for event in recorded] == [MessageEvent, SentMessageEvent]
    announced, reported = recorded
    assert isinstance(announced, MessageEvent)
    assert announced.message is sent.original_message
    assert isinstance(reported, SentMessageEvent)
    assert reported.message is sent
