"""The server failed to answer the request: a 5xx came back."""

from __future__ import annotations

from .http_error import HttpError

__all__ = ["ServerError"]


class ServerError(HttpError):
    """A 5xx status: the request may have been fine, the server was not.

    The far side is at fault, so the same request may well succeed later.
    Nothing here retries; what to do about it is the caller's to decide.
    """
