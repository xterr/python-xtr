"""Every notification message the request sent or queued."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Final, final

from xtr_clock import MonotonicClock
from xtr_http_kernel.data_collector import RequestTrace

from .notified_message import NotifiedMessage

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_http_kernel.data_collector import ProfiledRequest

    from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent
    from xtr_notifier.message import MessageInterface

__all__ = ["NotifierDataCollector"]

_NAME: Final = "notifier"


@final
class NotifierDataCollector:
    """Keeps the messages the request announced, and what each came to.

    It listens to the message events itself: :meth:`on_message` records a
    message as it is announced — sent now or queued — and
    :meth:`on_sent_message` and :meth:`on_failed_message` complete the
    record of the same message once its transport reports. The records go
    into a trace the collector owns and starts as each profiled request
    arrives, so concurrent requests never see each other's messages and an
    unprofiled one records nothing. The trace is read once everything has
    been sent, so a message sent while the body streamed, or by a listener
    after it, is there too.
    """

    __slots__ = ("_clock", "_trace")

    def __init__(self, clock: ClockInterface | None = None) -> None:
        """Time each send on ``clock``, a monotonic one unless given another."""
        self._clock: ClockInterface = MonotonicClock() if clock is None else clock
        self._trace: RequestTrace[NotifiedMessage] = RequestTrace("notifier_messages")

    @property
    def name(self) -> str:
        """``"notifier"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start recording the request that just arrived."""
        self._trace.begin()

    def on_message(self, event: MessageEvent) -> None:
        """Record the message ``event`` announces, when a profiled request is recorded."""
        if self._trace.is_recording():
            self._trace.record(
                NotifiedMessage.announced(event.message, queued=event.queued, at=self._clock.now())
            )

    def on_sent_message(self, event: SentMessageEvent) -> None:
        """Mark the message ``event`` reports as sent."""
        notified = self._pending(event.message.original_message)
        if notified is not None:
            notified.mark_sent(event.message, self._clock.now())

    def on_failed_message(self, event: FailedMessageEvent) -> None:
        """Mark the message ``event`` reports as failed."""
        notified = self._pending(event.message)
        if notified is not None:
            notified.mark_failed(event.error, self._clock.now())

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return what was announced so far; the rest follows once the response has left."""
        del profiled
        return self._read()

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every message the request sent or queued."""
        del data, profiled
        return self._read()

    def _pending(self, message: MessageInterface) -> NotifiedMessage | None:
        """Return the latest record of ``message`` still waiting for its transport's report.

        ``None`` outside a profiled request, or for a message announced before
        the request began.
        """
        return next(
            (
                notified
                for notified in reversed(self._trace.entries())
                if notified.message is message and notified.status == "pending"
            ),
            None,
        )

    def _read(self) -> dict[str, object]:
        notified = self._trace.entries()
        statuses = Counter(entry.status for entry in notified)
        return {
            "messages": [entry.to_data() for entry in notified],
            "count": len(notified),
            "queued": statuses["queued"],
            "sent": statuses["sent"],
            "failed": statuses["failed"],
            "by_transport": dict(
                Counter(entry.transport for entry in notified if entry.transport is not None)
            ),
        }
