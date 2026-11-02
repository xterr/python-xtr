"""Records every email event, for tests to assert on."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_mailer.event.message_events import MessageEvents

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mailer.event import MessageEvent

__all__ = ["MessageLoggerListener"]


@final
class MessageLoggerListener(ResetInterface):
    """Keeps every :class:`~xtr_mailer.event.MessageEvent` dispatched, until reset.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`, the lowest, so it records the email as the other listeners left it. A
    test then reads :meth:`get_events` to say what was sent or queued. Resetting it between
    units of work keeps one request's emails out of the next one's assertions.
    """

    #: Run after every other listener of the event.
    PRIORITY: Final = -255

    __slots__: ClassVar[tuple[str, ...]] = ("_disabled", "_events")

    def __init__(self, disabled: Callable[[], bool] | None = None) -> None:
        """Record events, except while ``disabled`` answers ``True``.

        Args:
            disabled: Asked before each event; recording stops while it answers ``True``.
                ``None`` always records.
        """
        self._disabled: Callable[[], bool] | None = disabled
        self._events: MessageEvents = MessageEvents()

    def get_events(self) -> MessageEvents:
        """Return what was recorded since the last reset."""
        return self._events

    def on_message(self, event: MessageEvent) -> None:
        """Record ``event``, unless recording is disabled right now."""
        if self._disabled is not None and self._disabled():
            return
        self._events.add(event)

    @override
    async def reset(self) -> None:
        """Forget everything recorded."""
        self._events = MessageEvents()
