from __future__ import annotations

from dataclasses import dataclass

import pytest
from xtr_messenger.stamp import StampInterface

from tests.support.recording_bus import RecordingBus

pytestmark = pytest.mark.anyio


@dataclass(frozen=True, slots=True)
class _Stamp(StampInterface):
    pass


async def test_it_keeps_each_message_with_its_stamps() -> None:
    bus, stamp = RecordingBus(), _Stamp()

    envelope = await bus.dispatch("message", stamp)

    assert bus.dispatched == [("message", (stamp,))]
    assert envelope.message == "message"
    assert envelope.stamps == (stamp,)


async def test_it_raises_the_error_it_is_given_and_keeps_nothing() -> None:
    bus = RecordingBus()
    bus.error = RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        _ = await bus.dispatch("message")

    assert bus.dispatched == []
