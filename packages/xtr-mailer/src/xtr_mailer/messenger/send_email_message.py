"""An email queued on a message bus, to be sent by a worker."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_mime import RawMessage

from xtr_mailer.envelope import Envelope

__all__ = ["SendEmailMessage"]


@dataclass(frozen=True, slots=True)
class SendEmailMessage:
    """An email and the envelope it is sent with, as the mailer queued them.

    Attributes:
        message: The email as the caller gave it, before any listener changed it.
        envelope: The envelope the caller gave; ``None`` sends with the one the email's
            headers give when it is sent.
    """

    message: RawMessage
    envelope: Envelope | None = None
