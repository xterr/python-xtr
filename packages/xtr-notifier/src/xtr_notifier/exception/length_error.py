"""A value longer than a provider accepts."""

from __future__ import annotations

from .logic_error import LogicError

__all__ = ["LengthError"]


class LengthError(LogicError):
    """A value is longer than the provider it is going to accepts — a subject, a button label.

    A logic error rather than a runtime one: the same value fails the same way
    every time, so it is fixed where the message is built, not retried.
    """
