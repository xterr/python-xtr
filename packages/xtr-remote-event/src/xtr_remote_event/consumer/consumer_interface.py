"""What an event from another system is handed to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_remote_event.remote_event import RemoteEvent

__all__ = ["ConsumerInterface"]


@runtime_checkable
class ConsumerInterface(Protocol):
    """Does whatever this application does with the events of a source.

    One method, returning nothing: a consumer is the end of the line, not a
    step in a chain. Which sources it answers for is not its business either —
    that is declared beside the class with ``as_remote_event_consumer``, so one
    consumer can serve several sources, and a source can be moved to another
    consumer without either of them changing.

    Async because consuming is where the work is: a row written, a mail sent,
    a call back to the sender.
    """

    async def consume(self, event: RemoteEvent) -> None:
        """Do what this application does with ``event``."""
        ...
