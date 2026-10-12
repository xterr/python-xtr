from __future__ import annotations

import pytest
from xtr_messenger import Envelope, MessageBusInterface

from tests.support.recording_message_bus import RecordingMessageBus


def test_it_is_a_bus_anything_can_dispatch_through() -> None:
    assert isinstance(RecordingMessageBus(), MessageBusInterface)


@pytest.mark.anyio
async def test_it_keeps_every_message_it_was_handed_in_order() -> None:
    bus = RecordingMessageBus()

    _ = await bus.dispatch("first")
    _ = await bus.dispatch("second")

    assert bus.messages == ["first", "second"]


@pytest.mark.anyio
async def test_it_hands_back_an_envelope_around_the_message() -> None:
    assert await RecordingMessageBus().dispatch("a message") == Envelope("a message", ())


@pytest.mark.anyio
async def test_it_fails_a_dispatch_it_was_built_to_fail() -> None:
    failure = RuntimeError("nothing handles this")
    bus = RecordingMessageBus(raises=failure)

    with pytest.raises(RuntimeError) as caught:
        _ = await bus.dispatch("a message")

    assert caught.value is failure


@pytest.mark.anyio
async def test_a_dispatch_that_failed_is_still_recorded() -> None:
    bus = RecordingMessageBus(raises=RuntimeError("nothing handles this"))

    with pytest.raises(RuntimeError):
        _ = await bus.dispatch("a message")

    assert bus.messages == ["a message"]
