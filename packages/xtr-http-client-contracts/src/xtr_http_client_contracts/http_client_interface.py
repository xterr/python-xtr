"""The calls code that sends an HTTP request depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import Unpack

if TYPE_CHECKING:
    from xtr_http_message_contracts import RequestInterface

    from .http_response_interface import HttpResponseInterface
    from .request_options import RequestOptions

__all__ = ["HttpClientInterface"]


@runtime_checkable
class HttpClientInterface(Protocol):
    """Sends HTTP requests and hands back responses.

    A library that calls out takes this interface, and the application
    decides what is behind it — a real transfer, a scoped client, a guard, or
    a client answering from memory in a test.

    ```python
    response = await client.request("GET", "https://example.com/orders")
    orders = await response.to_array()
    ```

    Several requests run at once by being made from tasks of one task group.

    An option name the contract does not list is refused with
    :class:`InvalidArgumentError
    <xtr_http_client_contracts.exception.invalid_argument_error.InvalidArgumentError>`:
    ``Unsupported option "foo" passed to "<client class>", did you mean "..."?``.
    An option that was spelled wrong cannot pass for one that was obeyed.
    """

    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request, and return once the status line and the headers are in.

        The same as :meth:`send_request` with a message request carrying
        ``method`` and ``url``, no headers and an empty body.

        It never raises because of the status: a 404 or a 503 is an answer,
        and comes back as a response.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to the
                ``base_uri`` option.
            **options: How the request is to be made; anything left out
                falls back to this client's defaults.

        Returns:
            The response, with its status and headers already in.

        Raises:
            TransportTimeoutError: When no answer came in time.
            InvalidArgumentError: For an invalid method, URL or option, before
                anything is sent.
            TransportError: When no answer came.
        """
        ...

    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send a message request, the options filling what it leaves out.

        The request is authoritative:

        - a relative URI is resolved against ``base_uri``;
        - ``query`` is merged into the URI;
        - a header from ``headers`` is sent only when the request has none of
          that name;
        - ``auth_basic`` and ``auth_bearer`` apply only when the request has
          no ``Authorization`` header;
        - ``body`` or ``json`` with a request whose body is not empty is
          refused: ``Define either the request body or the "body" or "json"
          option, setting both is not supported.``.

        It returns, and never raises because of the status, as
        :meth:`request` does.

        Args:
            request: The request to send.
            **options: What the request leaves out; anything left out of
                both falls back to this client's defaults.

        Returns:
            The response, with its status and headers already in.

        Raises:
            TransportTimeoutError: When no answer came in time.
            InvalidArgumentError: For an invalid method, URL or option, and for
                a body given both with the request and as an option, before
                anything is sent.
            TransportError: When no answer came.
        """
        ...

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a client whose requests start from these options.

        Args:
            **options: The defaults of the client returned, merged over this
                client's own, so what is left out is kept.

        Returns:
            A new client; this one is left as it was.

        Raises:
            InvalidArgumentError: When an option is invalid, as in :meth:`request`.
        """
        ...
