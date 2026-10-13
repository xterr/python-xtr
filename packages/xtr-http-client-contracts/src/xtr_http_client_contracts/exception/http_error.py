"""A server answered, and the answer was not a success."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .http_client_error import HttpClientError

if TYPE_CHECKING:
    from xtr_http_client_contracts.http_response_interface import HttpResponseInterface

__all__ = ["HttpError"]


class HttpError(HttpClientError):
    """The status code says the request did not get what it asked for.

    Never raised by making the request: a status is an answer, not a failure
    of the transfer, so it reaches the caller as a response. This is raised
    where the caller asks to be told about it —
    :meth:`HttpResponseInterface.get_content
    <xtr_http_client_contracts.http_response_interface.HttpResponseInterface.get_content>`
    or :meth:`HttpResponseInterface.to_array
    <xtr_http_client_contracts.http_response_interface.HttpResponseInterface.to_array>`
    with ``throw``.

    Catch this to handle any unsuccessful status;
    :class:`RedirectionError <...redirection_error.RedirectionError>`,
    :class:`ClientError <...client_error.ClientError>` and
    :class:`ServerError <...server_error.ServerError>` are the three ranges,
    and they are siblings, so catching one leaves the others alone.

    The response comes along because it is the only place the answer is left:
    the status code, the headers and the body, which is kept.

    Attributes:
        response: The response that was answered with.
        reason: What the status means for this request, naming the code and
            the URL. The message is this, composed by whoever raised it —
            the body of an error document is the most useful thing to put
            there and reading it is awaited, which a constructor cannot do.
    """

    response: HttpResponseInterface
    reason: str

    def __init__(self, response: HttpResponseInterface, reason: str) -> None:
        """Record the response the status came on, and what it means."""
        self.response = response
        self.reason = reason
        super().__init__(reason)
