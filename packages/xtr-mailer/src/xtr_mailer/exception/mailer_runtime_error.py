"""Something the mailer depends on failed while it was sending."""

from __future__ import annotations

from .mailer_error import MailerError

__all__ = ["MailerRuntimeError"]


class MailerRuntimeError(MailerError, RuntimeError):
    """Something an email depends on failed while it was sent — a server, a process.

    The input was fine and the code is fine; the world did not cooperate. Raising
    one out of a message handler is what makes a message bus retry the send.
    """
