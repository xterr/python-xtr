"""The request was refused: a 4xx came back."""

from __future__ import annotations

from .http_error import HttpError

__all__ = ["ClientError"]


class ClientError(HttpError):
    """A 4xx status: the server understood the request and would not serve it.

    Retrying the same request unchanged gets the same answer, so this is the
    one range worth telling apart — a 401 asks for credentials, a 404 says
    there is nothing there, a 429 says to slow down.
    """
