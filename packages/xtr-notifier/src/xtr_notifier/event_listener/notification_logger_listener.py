"""Records every message event, for tests to assert on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_notifier.event.notification_events import NotificationEvents

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_notifier.event import MessageEvent

__all__ = ["NotificationLoggerListener"]


@final
class NotificationLoggerListener(ResetInterface):
    """Keeps every :class:`~xtr_notifier.event.MessageEvent` dispatched, until reset.

    Listen to :class:`~xtr_notifier.event.MessageEvent` with :meth:`on_notification`
    at :attr:`PRIORITY`, the lowest, so it records the message as the other
    listeners left it. A test then reads :attr:`events` to say what was sent or
    queued. Resetting it between units of work keeps one request's messages out
    of the next one's assertions.
    """

    #: Run after every other listener of the event.
    PRIORITY: Final = -255

    __slots__ = ("_disabled", "_events")

    def __init__(self, disabled: Callable[[], bool] | None = None) -> None:
        """Record events, except while ``disabled`` answers ``True``.

        Args:
            disabled: Asked before each event; recording stops while it answers
                ``True``. ``None`` always records.
        """
        self._disabled = disabled
        self._events = NotificationEvents()

    @property
    def events(self) -> NotificationEvents:
        """What was recorded since the last reset."""
        return self._events

    def on_notification(self, event: MessageEvent) -> None:
        """Record ``event``, unless recording is disabled right now."""
        if self._disabled is not None and self._disabled():
            return
        self._events.add(event)

    @override
    async def reset(self) -> None:
        """Forget everything recorded."""
        self._events = NotificationEvents()
