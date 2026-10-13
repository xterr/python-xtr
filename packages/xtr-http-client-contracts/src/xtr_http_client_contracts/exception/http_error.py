"""A server answered, and the answer was not a success."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .http_client_error import HttpClientError

if TYPE_CHECKING:
    from xtr_http_client_contracts.response_interface import ResponseInterface

__all__ = ["HttpError"]


class HttpError(HttpClientError):
    """The status code says the request did not get what it asked for.

    Never raised by making the request: a status is an answer, not a failure
    of the transfer, so it reaches the caller as a response. This is raised
    where the caller asks to be told about it —
    :meth:`ResponseInterface.get_content
    <xtr_http_client_contracts.response_interface.ResponseInterface.get_content>`
    or :meth:`ResponseInterface.to_array
    <xtr_http_client_contracts.response_interface.ResponseInterface.to_array>`
    with ``throw``, or leaving an ``async with`` block over a response whose
    status nobody looked at.

    Catch this to handle any unsuccessful status;
    :class:`RedirectionError <...redirection_error.RedirectionError>`,
    :class:`ClientError <...client_error.ClientError>` and
    :class:`ServerError <...server_error.ServerError>` are the three ranges,
    and they are siblings, so catching one leaves the others alone.

    The response comes along because it is the only place the answer is left:
    the status code, the headers and, when the body was kept, what the server
    said about it.

    Attributes:
        response: The response that was answered with.
        reason: What the status means for this request, naming the code and
            the URL. The message is this, composed by whoever raised it —
            the body of an error document is the most useful thing to put
            there and reading it is awaited, which a constructor cannot do.
    """

    response: ResponseInterface
    reason: str

    def __init__(self, response: ResponseInterface, reason: str) -> None:
        """Record the response the status came on, and what it means."""
        self.response = response
        self.reason = reason
        super().__init__(reason)
