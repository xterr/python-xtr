"""Every email a profiled request sent or queued, and how each send ended."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_http_kernel.data_collector import RequestTrace

from ._mail_record import MailRecord
from ._message_data import message_data

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_kernel.data_collector import ProfiledRequest
    from xtr_mime import RawMessage

    from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent

__all__ = ["MailerDataCollector"]

_NAME: Final = "mailer"


@final
class MailerDataCollector:
    """Hears every email event of a profiled request, and keeps each email with how it ended.

    It listens to the events itself: :meth:`on_message` records each announced email,
    :meth:`on_sent` and :meth:`on_failed` complete the record of the very message the
    transport sent or failed to. The announcement is heard before any other listener, at
    :attr:`PRIORITY`, so an email a listener rejects — which stops the event there — is
    recorded too; the record keeps the event, and is read once the listeners all ran.

    The records belong to the request being profiled: two requests served at once each see
    their own emails, and an email sent outside a profiled request is not kept at all.
    Nothing is read off a message until :meth:`late_collect`, once the response has left, so
    the panel adds no work to a send.
    """

    #: Run before every other listener of the announcement, so a rejection is seen too.
    PRIORITY: ClassVar[int] = 1024

    __slots__ = ("_trace",)

    def __init__(self) -> None:
        """Keep no email until a profiled request begins."""
        self._trace: RequestTrace[MailRecord] = RequestTrace("mailer_messages")

    @property
    def name(self) -> str:
        """``"mailer"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start keeping the emails of the request that just arrived."""
        self._trace.begin()

    def on_message(self, event: MessageEvent) -> None:
        """Record the email ``event`` announces, when a profiled request is being handled."""
        if self._trace.is_recording():
            self._trace.record(MailRecord(event))

    def on_sent(self, event: SentMessageEvent) -> None:
        """Mark the email the transport sent as sent, with what it learned sending it."""
        sent = event.get_message()
        record = self._record_of(sent.get_original_message())
        if record is not None:
            record.sent = sent

    def on_failed(self, event: FailedMessageEvent) -> None:
        """Mark the email the transport failed to send as failed, with the error."""
        record = self._record_of(event.get_message())
        if record is not None:
            record.error = event.get_error()

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the counts so far; the emails follow once the response has left."""
        del profiled
        return _counts(self._trace.entries())

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every email of the request, in the order announced, and the counts."""
        del data, profiled
        records = self._trace.entries()
        return {"messages": [message_data(record) for record in records], **_counts(records)}

    def _record_of(self, message: RawMessage) -> MailRecord | None:
        """Return the latest record of ``message`` itself, ``None`` outside a profiled request."""
        return next(
            (record for record in reversed(self._trace.entries()) if record.is_for(message)), None
        )


def _counts(records: Sequence[MailRecord]) -> dict[str, object]:
    statuses = [record.status() for record in records]
    return {
        "count": len(statuses),
        "queued": statuses.count("queued"),
        "sent": statuses.count("sent"),
        "failed": statuses.count("failed"),
    }
