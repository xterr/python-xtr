"""What sends an email."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.sent_message import SentMessage

__all__ = ["TransportInterface"]


@runtime_checkable
class TransportInterface(Protocol):
    """Sends an email now, and reports what it sent.

    Code sending email depends on the mailer instead, which may queue the email on a message
    bus; a transport is what the mailer, or the worker that takes the email off the bus,
    finally hands it to. Its string form names it in errors, logs and events, so it never
    carries a credential: ``smtp://smtp.example.com:587``, not the password.
    """

    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send ``message`` with ``envelope``, or the envelope its headers give.

        Returns ``None`` when the email was not sent because a listener rejected it.
        Implementations raise :class:`~xtr_mailer.exception.TransportError` when the server
        cannot be reached or refuses the email — the one failure a failover transport tries
        another transport for.
        """
        ...
