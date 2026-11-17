"""One message a profiled request sent or queued, as the panel shows it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, final

from xtr_http_kernel.data_collector import clone_var

from xtr_notifier.message import (
    ChatMessage,
    MessageInterface,
    NullMessage,
    PushMessage,
    SentMessage,
    SmsMessage,
)

from ._masking import masked

__all__ = ["NotifiedMessage"]

_MILLISECONDS_PER_SECOND = 1000.0


@final
@dataclass(slots=True, eq=False)
class NotifiedMessage:
    """What one message carried, and what came of it.

    Recorded when the message is announced — about to be sent, or queued —
    so messages keep the order they left in, and completed when the
    transport reports it sent or failed. A failover transport announces each
    attempt, so each attempt is a message of its own. Everything the panel
    shows is plain data already, the options cloned and masked when recorded;
    the message itself is kept only to match the transport's report to it,
    and never reaches the profile.

    Attributes:
        message: The message announced, matched by identity to the report.
        started_at: When it was announced, to time the send.
        message_class: The message's qualified class name.
        channel: ``"chat"``, ``"sms"`` or ``"push"``, after the kind of message —
            the wrapped one, for a message the null transport sent nowhere;
            ``None`` for a kind of its own.
        transport: The transport the message names, ``None`` for the first that can.
        subject: The text every provider shows.
        recipient: Who it goes to on the provider — a phone number, a chat —
            or ``None`` for the transport's default.
        options: The provider's options as a masked
            :func:`~xtr_http_kernel.data_collector.clone_var` tree, ``None`` for none.
        queued: Whether it was handed to a message bus instead of sent now.
        status: ``"queued"``, ``"pending"`` until the transport reports, then
            ``"sent"`` or ``"failed"``.
        sent_through: The transport that sent it, as it names itself.
        sent_message_id: The id the provider gave it, when it gave one.
        error: Why it was not sent, as ``"<error class>: <message>"``.
        duration_ms: How long the send took; ``None`` until it is reported.
    """

    message: MessageInterface
    started_at: datetime
    message_class: str
    channel: Literal["chat", "sms", "push"] | None
    transport: str | None
    subject: str
    recipient: str | None
    options: dict[str, object] | None
    queued: bool
    status: Literal["queued", "pending", "sent", "failed"]
    sent_through: str | None = None
    sent_message_id: str | None = None
    error: str | None = None
    duration_ms: float | None = None

    @classmethod
    def announced(cls, message: MessageInterface, *, queued: bool, at: datetime) -> NotifiedMessage:
        """Record ``message`` as announced ``at``, queued or about to be sent."""
        options = message.options
        klass = type(message)
        return cls(
            message=message,
            started_at=at,
            message_class=f"{klass.__module__}.{klass.__qualname__}",
            channel=_channel(message),
            transport=message.transport,
            subject=message.subject,
            recipient=message.recipient_id,
            options=None if options is None else masked(clone_var(options)),
            queued=queued,
            status="queued" if queued else "pending",
        )

    def mark_sent(self, sent: SentMessage, at: datetime) -> None:
        """Complete the record with what the transport reported ``at``."""
        self.status = "sent"
        self.sent_through = sent.transport
        self.sent_message_id = sent.message_id
        self.duration_ms = self._elapsed_ms(at)

    def mark_failed(self, error: Exception, at: datetime) -> None:
        """Complete the record with the error the transport failed with ``at``."""
        self.status = "failed"
        self.error = f"{type(error).__name__}: {error}"
        self.duration_ms = self._elapsed_ms(at)

    def to_data(self) -> dict[str, object]:
        """Return the message as the JSON-safe mapping a profile keeps."""
        return {
            "message_class": self.message_class,
            "channel": self.channel,
            "transport": self.transport,
            "subject": self.subject,
            "recipient": self.recipient,
            "options": self.options,
            "queued": self.queued,
            "status": self.status,
            "sent_through": self.sent_through,
            "sent_message_id": self.sent_message_id,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    def _elapsed_ms(self, at: datetime) -> float:
        return (at - self.started_at).total_seconds() * _MILLISECONDS_PER_SECOND


def _channel(message: MessageInterface) -> Literal["chat", "sms", "push"] | None:
    match message:
        case ChatMessage():
            return "chat"
        case SmsMessage():
            return "sms"
        case PushMessage():
            return "push"
        case NullMessage():
            return _channel(message.message)
        case _:
            return None
