from __future__ import annotations

import pytest
from xtr_messenger import Envelope, MessageBusInterface

from tests.support.recording_message_bus import RecordingMessageBus

pytestmark = pytest.mark.anyio


def test_it_is_a_message_bus() -> None:
    assert isinstance(RecordingMessageBus(), MessageBusInterface)


async def test_it_keeps_every_message_in_order_and_hands_back_an_envelope() -> None:
    bus = RecordingMessageBus()

    first = await bus.dispatch("first")
    _ = await bus.dispatch("second")

    assert bus.messages == ["first", "second"]
    assert first == Envelope("first", ())
