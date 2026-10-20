"""A value handed to the notifier that cannot be used."""

from __future__ import annotations

from .notifier_error import NotifierError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(NotifierError, ValueError):
    """A value handed to this library cannot be used: a malformed DSN, an empty phone number.

    Also a :class:`ValueError`, so code that already guards against a bad value
    catches it without knowing this library exists.
    """
