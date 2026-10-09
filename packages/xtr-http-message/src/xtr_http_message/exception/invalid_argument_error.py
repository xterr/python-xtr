"""An argument cannot be what it is being used as."""

from __future__ import annotations

from .http_message_error import HttpMessageError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(HttpMessageError, ValueError):
    """An argument's value rules it out: a malformed header name, an out-of-range port.

    It derives from :class:`ValueError` as well as from
    :class:`~xtr_http_message.exception.http_message_error.HttpMessageError`
    because that is what the contract promises a caller: code written against
    the interfaces catches the builtin and never names this package.
    """
