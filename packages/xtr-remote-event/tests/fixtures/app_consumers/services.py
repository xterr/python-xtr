"""One consumer answering for two sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_remote_event.decorator import as_remote_event_consumer

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

TEST = "test"
OTHER = "other"


@as_remote_event_consumer(OTHER)
@as_remote_event_consumer(TEST)
class BothSourcesConsumer:
    """Keeps every event it was handed, whichever of its two sources it came from."""

    def __init__(self) -> None:
        """Start with nothing consumed."""
        self.consumed: list[RemoteEvent] = []

    async def consume(self, event: RemoteEvent) -> None:
        """Keep ``event``, so a test can say which arrived and in what order."""
        self.consumed.append(event)
