"""The root every error of the HTTP client contract derives from."""

from __future__ import annotations

__all__ = ["HttpClientError"]


class HttpClientError(Exception):
    """Base class for every error raised through the HTTP client contract.

    Catch this to handle anything calling out can go wrong with, whichever
    client is behind the interface; catch a subclass to handle one cause.
    Every subclass carries what a caller needs as typed attributes and
    composes its message from them.

    A server answering is not a cause: a request that came back with a 404 or
    a 503 succeeded as a transfer, so ``request()`` returns the response and
    nothing is raised until someone reads its content and asks to be told.
    What raises on its own is the transfer failing, a body that will not
    decode, and an option no client here understands.
    """
