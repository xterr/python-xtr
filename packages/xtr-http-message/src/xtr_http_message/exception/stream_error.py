"""A stream cannot do what is being asked of it now."""

from __future__ import annotations

from .http_message_error import HttpMessageError

__all__ = ["StreamError"]


class StreamError(HttpMessageError, RuntimeError):
    """A stream operation cannot be carried out: detached, not seekable, not readable.

    It derives from :class:`RuntimeError` as well as from
    :class:`~xtr_http_message.exception.http_message_error.HttpMessageError`
    because that is what the contract promises a caller: code written against
    the interfaces catches the builtin and never names this package.
    """
