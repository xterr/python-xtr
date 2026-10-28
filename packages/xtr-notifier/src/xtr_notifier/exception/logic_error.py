"""The notifier used in a way that cannot work."""

from __future__ import annotations

from .notifier_error import NotifierError

__all__ = ["LogicError"]


class LogicError(NotifierError, RuntimeError):
    """This library was used in a way that cannot work, whatever the message carries.

    A message no configured transport supports, a transport handed a message type
    it was never built for: each is a mistake in the code or the configuration,
    so retrying it changes nothing.
    """
