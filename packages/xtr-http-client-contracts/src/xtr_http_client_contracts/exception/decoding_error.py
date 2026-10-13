"""The body arrived whole but is not what it was being read as."""

from __future__ import annotations

from .http_client_error import HttpClientError

__all__ = ["DecodingError"]


class DecodingError(HttpClientError, ValueError):
    """A body could not be turned into the shape that was asked for.

    What :meth:`HttpResponseInterface.to_array
    <xtr_http_client_contracts.http_response_interface.HttpResponseInterface.to_array>`
    raises when the body is empty, is not JSON, or is JSON that is not an
    object. The transfer succeeded, so this is about the payload, not the
    connection.

    Also a :class:`ValueError`, so code that already guards what it parses
    with ``except ValueError`` keeps working without learning a new
    exception.

    Attributes:
        reason: What is wrong with the body, naming the URL it came from.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the body."""
        self.reason = reason
        super().__init__(reason)
