"""The one call code that sends an HTTP request depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from typing_extensions import Unpack

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .request_options import RequestOptions
    from .response_interface import ResponseInterface
    from .response_stream_interface import ResponseStreamInterface

__all__ = ["HttpClientInterface"]


@runtime_checkable
class HttpClientInterface(Protocol):
    """Sends HTTP requests and hands back responses.

    One call makes a request; everything else is a way of reading what came
    back or of fixing what the next request will ask for. A library that
    calls out takes this interface, and the application decides what is
    behind it — a real transfer, a scoped client, a guard, or a client
    answering from memory in a test.

    ```python
    response = await client.request("GET", "https://example.com/orders")
    orders = await response.to_array()
    ```

    Every client here is also every other client's decorator: scoping,
    refusing private addresses and following redirects are clients wrapping a
    client, so they compose in any order and no one of them sits above the
    rest.

    A client need not support every option, and it says which it cannot by
    raising :class:`TransportError
    <xtr_http_client_contracts.exception.transport_error.TransportError>` for
    it. That is the difference between an option a client ignores and one it
    has never heard of — silence would make the two look the same.
    """

    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> ResponseInterface:
        """Make a request, and return as soon as the answer starts arriving.

        This returns once the status line and the headers are in. The body
        follows, read when somebody asks for it, so a large response costs
        nothing until it is wanted and a response nobody reads costs only the
        connection it holds.

        It never raises because of the status: a 404 or a 503 is an answer,
        and comes back as a response. What raises is the transfer failing and
        an option this client cannot honour.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to the
                ``base_uri`` option.
            **options: How the request is to be made. See
                :class:`RequestOptions
                <xtr_http_client_contracts.request_options.RequestOptions>`;
                anything left out falls back to this client's defaults.

        Returns:
            The response, with its status and headers already in.

        Raises:
            TransportError: When the request could not be made or nothing
                usable came back, and when an option is one this client does
                not support.
        """
        ...

    def stream(
        self,
        responses: ResponseInterface | Iterable[ResponseInterface],
        timeout: float | None = None,
    ) -> ResponseStreamInterface:
        """Read several responses at once, chunk by chunk as they arrive.

        Nothing is transferred until the stream is iterated, which is why
        this is not awaited.

        Args:
            responses: One response this client made, or any number of them.
            timeout: How long the run may go quiet for before it yields a
                timeout chunk, in seconds. ``None`` uses each response's own
                ``timeout`` option.

        Returns:
            The chunks of every response, each paired with the response it
            arrived for.
        """
        ...

    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a client whose requests start from these options.

        This client is left as it was, so one client can be configured
        differently for each caller it is handed to without any of them
        affecting the others.

        Args:
            **options: The defaults of the client returned. They are merged
                over this client's own, so what is left out is kept.

        Returns:
            A new client; this one is left as it was.

        Raises:
            TransportError: When an option is one this client does not
                support — the same rule as :meth:`request`, so a caller
                learns about it when configuring rather than on the first
                request.
        """
        ...
