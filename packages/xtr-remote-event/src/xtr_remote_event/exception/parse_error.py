"""A payload could not be read as an event."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError

__all__ = ["ParseError"]


class ParseError(InvalidArgumentError):
    """A converter was handed a payload it cannot read as an event.

    A kind of invalid argument, and typed separately because the caller does
    something different about it: a payload that cannot be read is the
    sender's doing, and the answer is to tell the sender, not to fix the
    application.
    """
