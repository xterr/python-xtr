"""The client that holds a request back until the rate it is under allows it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_service_contracts import ResetInterface

if TYPE_CHECKING:
    from typing import Self

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions
    from xtr_http_message_contracts import RequestInterface
    from xtr_rate_limiter import LimiterInterface

__all__ = ["ThrottlingHttpClient"]


@final
class ThrottlingHttpClient(HttpClientInterface, ResetInterface):
    """Wraps a client and lets each request go only once the rate allows it.

    An API that answers a hundred calls a minute answers the hundred and
    first with a refusal, and a caller that keeps asking is throttled by the
    service it is calling rather than by itself. Written at the call site
    that is a counter and a sleep around every request; here it is the client,
    so the code calling out is unchanged and the pace is kept in one place —
    including between several callers, when the limiter they share counts
    where they can all see it.

    ```python
    client = ThrottlingHttpClient(inner, limiter)
    async with await client.request("GET", "https://api.example.com/orders") as response:
        orders = await response.to_array()
    ```

    A token is booked before each request, and the request waits for the
    moment that booking is due. Booking first and waiting after is what makes
    the pace hold under concurrency: the limiter counts the token as spent as
    soon as it is reserved, so requests leave in the order they were asked
    for, each at its own turn, rather than all at once as a limiter merely
    asked whether it may go ahead would allow.

    The limiter is the pace, so a copy made by :meth:`with_options` shares it:
    narrowing a client for one job hands out another way of making requests,
    not another allowance to make them.
    """

    __slots__ = ("_client", "_limiter")

    def __init__(self, client: HttpClientInterface, limiter: LimiterInterface) -> None:
        """Pace what ``client`` sends by ``limiter``.

        Args:
            client: The client every request is handed to, once it is due.
            limiter: What a token is booked from before each request. Which
                requests share a pace is decided by which of them are given
                the same limiter — one per host, one per account, one for
                the whole application.
        """
        self._client = client
        self._limiter = limiter

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request for ``method`` and ``url``, once a token is due.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to a ``base_uri``.
            **options: How the request is to be made.

        Returns:
            Whatever the wrapped client answers.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came.
        """
        await self._due()

        return await self._client.request(method, url, **options)

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send ``request``, once a token is due.

        Args:
            request: The request to send.
            **options: What the request leaves out.

        Returns:
            Whatever the wrapped client answers.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came.
        """
        await self._due()

        return await self._client.send_request(request, **options)

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a copy around a wrapped client whose defaults have ``options`` over them.

        Args:
            **options: The defaults of the wrapped client of the copy.

        Returns:
            A new client, paced by this one's limiter, so requests made
            through either count against the same rate; this one is left as
            it was.

        Raises:
            InvalidArgumentError: When an option is invalid.
        """
        return type(self)(self._client.with_options(**options), self._limiter)

    @override
    async def reset(self) -> None:
        """Forget every request counted against the rate, and reset the wrapped client."""
        await self._limiter.reset()

        if isinstance(self._client, ResetInterface):
            await self._client.reset()

    async def _due(self) -> None:
        """Book a token and wait for the moment it may be spent."""
        reservation = await self._limiter.reserve()

        await reservation.wait()
