from __future__ import annotations

import pytest

from tests.support.dummy_message import DummyMessage
from tests.support.recorded_events import recording_dispatcher
from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_notifier.message import SentMessage

pytestmark = pytest.mark.anyio


async def test_it_records_every_notifier_event_in_order() -> None:
    dispatcher, recorded = recording_dispatcher()
    message = DummyMessage()
    events = [
        MessageEvent(message),
        SentMessageEvent(SentMessage(message, "t")),
        FailedMessageEvent(message, RuntimeError()),
    ]

    for event in events:
        _ = await dispatcher.dispatch(event)

    assert recorded == events
