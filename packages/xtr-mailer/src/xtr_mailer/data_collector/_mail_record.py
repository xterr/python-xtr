"""One email a profiled request sent or queued, completed as its later events arrive."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer.event import MessageEvent
    from xtr_mailer.sent_message import SentMessage

__all__ = ["MailRecord", "Status"]

type Status = Literal["queued", "sent", "failed", "rejected", "pending"]
"""Where an email stands: handed to the bus, taken, refused, rejected by a listener, or none yet."""


@final
class MailRecord:
    """The announcement of an email, and how its send ended.

    The event itself is kept, not a copy of what it says: the listeners after the collector
    may still replace the message or reject the email, and the record is read once they all
    ran. The message the event was announced with is kept too, since a signing listener
    replaces it with one that no longer reads as an email.

    Attributes:
        event: The announcement, as the listeners left it.
        original: The message the event carried before any listener ran.
        sent: What the transport sent, once it did.
        error: Why the transport did not send it, once it failed.
    """

    __slots__ = ("error", "event", "original", "sent")

    def __init__(self, event: MessageEvent) -> None:
        """Record the email ``event`` announces, its send not ended yet."""
        self.event: MessageEvent = event
        self.original: RawMessage = event.get_message()
        self.sent: SentMessage | None = None
        self.error: Exception | None = None

    def is_for(self, message: RawMessage) -> bool:
        """Tell whether ``message`` is the very one the transport got from this announcement.

        A transport hands the message the listeners left on the event to the send, and
        reports that same object as sent or failed; identity tells two equal emails apart.
        """
        return self.event.get_message() is message

    def status(self) -> Status:
        """Return where the email stands, a rejection first: a rejected email is never sent."""
        if self.event.is_rejected():
            return "rejected"
        if self.error is not None:
            return "failed"
        if self.sent is not None:
            return "sent"
        if self.event.is_queued():
            return "queued"
        return "pending"
