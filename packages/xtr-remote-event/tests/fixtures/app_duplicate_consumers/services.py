"""Two consumers both claiming one source — the mistake the build refuses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_remote_event.decorator import as_remote_event_consumer

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

CLAIMED = "test"


@as_remote_event_consumer(CLAIMED)
class FirstConsumer:
    """Answers for the claimed source."""

    async def consume(self, event: RemoteEvent) -> None:
        """Consume nothing; the build never gets this far."""
        del event


@as_remote_event_consumer(CLAIMED)
class SecondConsumer:
    """Answers for the same source, which is what the build refuses."""

    async def consume(self, event: RemoteEvent) -> None:
        """Consume nothing; the build never gets this far."""
        del event
