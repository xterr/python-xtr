"""A listener that records the JWT events the served application dispatches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_jwt.event.jwt_authenticated_event import JwtAuthenticatedEvent
from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_event_dispatcher_contracts import Event

__all__ = ["EVENTS", "RecordingSubscriber"]

#: The names of the JWT events the served application dispatched, in order.
EVENTS: list[str] = []


@as_service
class RecordingSubscriber(EventSubscriberInterface):
    """Records the JWT lifecycle events the firewall dispatches, for the served tests."""

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to every JWT event the firewall dispatches."""
        return {
            JwtAuthenticatedEvent: "on_event",
            JwtInvalidEvent: "on_event",
            JwtExpiredEvent: "on_event",
            JwtNotFoundEvent: "on_event",
        }

    async def on_event(self, event: Event, event_name: str) -> None:
        """Record the event's name."""
        del event
        EVENTS.append(event_name)
