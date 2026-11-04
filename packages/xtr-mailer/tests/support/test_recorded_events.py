from __future__ import annotations

import pytest
from xtr_mime import Address, RawMessage

from tests.support.recorded_events import recording_dispatcher
from xtr_mailer import Envelope, SentMessage
from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent

pytestmark = pytest.mark.anyio


async def test_it_records_every_email_event_in_order() -> None:
    dispatcher, recorded = recording_dispatcher()
    message = RawMessage(b"")
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])
    events = [
        MessageEvent(message, envelope, "t"),
        SentMessageEvent(SentMessage(message, envelope)),
        FailedMessageEvent(message, RuntimeError()),
    ]

    for event in events:
        _ = await dispatcher.dispatch(event)

    assert recorded == events
