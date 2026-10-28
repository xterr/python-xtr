"""A value handed to the mailer that cannot be used."""

from __future__ import annotations

from .mailer_error import MailerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(MailerError, ValueError):
    """A value handed to this library cannot be used: a malformed DSN, an envelope with no sender.

    Also a :class:`ValueError`, so code that already guards against a bad value
    catches it without knowing this library exists.
    """
