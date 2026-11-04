"""A message put together in a way that cannot work."""

from __future__ import annotations

from .mime_error import MimeError

__all__ = ["LogicError"]


class LogicError(MimeError, RuntimeError):
    """This library was used in a way that cannot work, whatever the values involved.

    A message with no body, a part asked for something only another kind of part has:
    each is a mistake in the calling code, so trying again changes nothing.
    """
