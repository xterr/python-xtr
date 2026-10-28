"""The mailer used in a way that cannot work."""

from __future__ import annotations

from .mailer_error import MailerError

__all__ = ["LogicError"]


class LogicError(MailerError, RuntimeError):
    """This library was used in a way that cannot work, whatever the email carries.

    A DSN scheme no installed factory serves, a transport handed an email it was
    never built for: each is a mistake in the code or the configuration, so
    retrying it changes nothing.
    """
