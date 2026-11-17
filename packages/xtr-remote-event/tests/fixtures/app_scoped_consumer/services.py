"""A consumer living in the unit of the message it consumes, with that unit's session."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from xtr_dependency_injection import as_service

from xtr_remote_event.decorator import as_remote_event_consumer

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

__all__ = ["SOURCE", "ScopedConsumer", "Session"]

SOURCE = "scoped"


@final
@as_service(lifetime="scoped")
class Session:
    """Stands for a database session: one per unit of work."""


@final
@as_service(lifetime="scoped")
@as_remote_event_consumer(SOURCE)
class ScopedConsumer:
    """Remembers the session it was built with, and every event it was handed."""

    # Shared on purpose: each unit builds a new consumer.
    consumed: ClassVar[list[tuple[Session, RemoteEvent]]] = []

    def __init__(self, session: Session) -> None:
        """Keep the unit's ``session``."""
        self.session = session

    async def consume(self, event: RemoteEvent) -> None:
        """Note which session consumed ``event``."""
        ScopedConsumer.consumed.append((self.session, event))
