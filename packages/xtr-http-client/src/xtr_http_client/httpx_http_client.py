"""The client that opens the connections and streams what comes back."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast, final

import anyio
import httpx
from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_message import Request

from .http_client_mixin import HttpClientMixin
from .internal.httpx_clients import HttpxClients
from .internal.httpx_errors import timed_out, transport_error
from .internal.httpx_redirect import next_hop, same_origin
from .internal.httpx_request import (
    assemble_headers,
    assemble_payload,
    carries,
    pin_host,
    target_url,
)
from .response.httpx_response import to_http_response

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType
    from typing import Self

    from xtr_http_client_contracts import RequestOptions
    from xtr_http_message_contracts import RequestInterface

    from .response import HttpResponse

__all__ = ["HttpxHttpClient"]


@final
class HttpxHttpClient(HttpClientMixin, HttpClientInterface):
    """Sends requests over real connections, and hands back answers as they arrive.

    A request returns once the status line and the headers are in, whatever
    the status; the body is read off the connection when the caller asks for
    it, and the connection is held until the body is done with or the
    response is left.

    The request is authoritative and the options fill what it leaves out — a
    header it already carries is the one sent, credentials apply only where it
    has no ``Authorization`` of its own — which is what lets one set of
    client-wide defaults sit under requests that each know their own mind.
    What each part of an outgoing request is assembled from is in
    :mod:`xtr_http_client.internal.httpx_request`; what is here is the
    exchange, and the redirect chain it may turn into.

    Connections are pooled by how they connect rather than by host: a proxy,
    a trust store, a protocol version and the deadlines all decide what a
    connection is, so each combination of them gets a pool, and
    ``max_host_connections`` is each pool's ceiling across every host it
    reaches.

    ```python
    async with HttpxHttpClient(max_host_connections=4) as client:
        response = await client.request("GET", "https://example.com/orders")
        orders = await response.to_array()
    ```

    Redirects are followed here rather than by the backend, so that an
    ``Authorization`` header is dropped the moment a chain leaves the host it
    was meant for, and comes back only when the chain returns to it.
    """

    __slots__ = ("_clients",)

    def __init__(
        self,
        default_options: RequestOptions | None = None,
        max_host_connections: int = 6,
    ) -> None:
        """Start from ``default_options``, opening nothing until a request is made.

        Args:
            default_options: What every request this client makes starts
                from, over the contract's own defaults.
            max_host_connections: How many connections one pool may hold at
                once.

        Raises:
            InvalidArgumentError: When a default option is not one this
                client knows.
        """
        super().__init__(default_options)
        self._clients = HttpxClients(max_host_connections)

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponse:
        """Make a request for ``method`` and ``url``, and return once its head is in.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to ``base_uri``.
            **options: How the request is to be made.

        Returns:
            The response, with its status and headers already in.

        Raises:
            TransportTimeoutError: When no answer came in time.
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When no answer came.
        """
        self.validate_method(method)

        return await self.send_request(Request(method, _reachable(url)), **options)

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponse:
        """Send ``request``, the options filling what it leaves out.

        Args:
            request: The request to send.
            **options: What the request leaves out.

        Returns:
            The response, with its status and headers already in.

        Raises:
            TransportTimeoutError: When no answer came in time.
            InvalidArgumentError: For an invalid method, URL or option, and
                for a body given both with the request and as an option.
            TransportError: When no answer came.
        """
        self.validate_options(options)
        self.validate_method(request.get_method())
        merged = self.merge_default_options(options, self._default_options)
        self.validate_auth(merged)
        self.validate_body(merged)

        client, resolved = self._clients.for_options(merged)
        headers = assemble_headers(request, merged)
        payload = await assemble_payload(request, merged, headers)
        url, extensions = pin_host(target_url(request, merged), merged, resolved, headers)

        outgoing = client.build_request(
            request.get_method(),
            url,
            content=payload.content,
            data=payload.form,
            json=payload.document,
            headers=headers,
            extensions=extensions,
        )

        return await self._send(client, outgoing, merged, headers)

    async def aclose(self) -> None:
        """Close every pool, and with it every connection this client holds."""
        await self._clients.aclose()

    async def __aenter__(self) -> Self:
        """Enter a block that owns this client's connections.

        Returns:
            This client.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close every connection however the block ends.

        Args:
            exc_type: The class of the exception the block is leaving with.
            exc: That exception.
            traceback: Its traceback.
        """
        del exc_type, exc, traceback
        await self.aclose()

    async def _send(
        self,
        client: httpx.AsyncClient,
        outgoing: httpx.Request,
        options: Mapping[str, object],
        headers: Sequence[tuple[str, str]],
    ) -> HttpResponse:
        """Make the exchange, under whatever deadline the whole request was given."""
        url = str(outgoing.url)
        limit = _seconds(options.get("max_duration"))
        start_time = time.time()
        deadline = None if limit is None else anyio.current_time() + limit

        try:
            with anyio.fail_after(limit):
                response, history = await _exchange(
                    client,
                    outgoing,
                    _basic_credentials(options, headers),
                    _hops(options.get("max_redirects")),
                )
        except TimeoutError as error:
            raise timed_out(url) from error
        except (httpx.HTTPError, httpx.InvalidURL) as error:
            raise transport_error(error, url) from error

        return await to_http_response(
            response,
            history,
            response.request.method,
            start_time,
            options.get("user_data"),
            deadline=deadline,
            decode=not carries(headers, "accept-encoding"),
        )


async def _exchange(
    client: httpx.AsyncClient,
    outgoing: httpx.Request,
    auth: tuple[str, str] | None,
    max_redirects: int,
) -> tuple[httpx.Response, list[httpx.Response]]:
    """Send, then follow where each answer points until one points nowhere.

    Following is done here, a hop at a time, for the one thing the backend
    cannot be told: credentials belong to the host they were meant for, so an
    ``Authorization`` the backend dropped on the way out of that host is put
    back the moment the chain returns to it, and nowhere else.
    """
    response = await client.send(outgoing, auth=auth, stream=True, follow_redirects=False)
    history: list[httpx.Response] = []
    origin = response.request.url
    authorization = cast("str | None", response.request.headers.get("authorization"))

    while len(history) < max_redirects:
        following = next_hop(response)
        if following is None:
            break

        if (
            authorization is not None
            and "authorization" not in following.headers
            and same_origin(following.url, origin)
        ):
            following.headers["Authorization"] = authorization

        history.append(response)
        await response.aclose()
        response = await client.send(following, stream=True, follow_redirects=False)

    return response, history


def _reachable(url: str) -> str:
    """``url`` with every part of it written in the form that reaches it.

    A host named in another script is looked up in its ``xn--`` form, which
    is also the only form a message request will hold, so the conversion
    happens here — while the URL is still text — rather than further in,
    where it would surface as a URL nobody can parse.

    Raises:
        InvalidArgumentError: When the URL cannot be read at all.
    """
    if url.isascii():
        return url

    try:
        parsed = httpx.URL(url)

        return str(parsed.copy_with(host=parsed.raw_host.decode("ascii")))
    except (httpx.InvalidURL, UnicodeError) as error:
        raise transport_error(httpx.InvalidURL(str(error)), url) from error


def _basic_credentials(
    options: Mapping[str, object],
    headers: Sequence[tuple[str, str]],
) -> tuple[str, str] | None:
    """The user and password to authenticate with, when the request has no say.

    Credentials written into the URL are left where they are: the backend
    reads them off it, which is also what keeps them out of a redirect that
    leaves the host.
    """
    basic = options.get("auth_basic")
    if basic is None or carries(headers, "authorization"):
        return None

    if isinstance(basic, str):
        user, _, password = basic.partition(":")

        return user, password

    parts = [str(part) for part in cast("Sequence[object]", basic)]

    return parts[0], parts[1] if len(parts) > 1 else ""


def _seconds(value: object) -> float | None:
    """A limit in seconds, or ``None`` when zero said there is none."""
    if isinstance(value, (int, float)) and value > 0:
        return float(value)

    return None


def _hops(value: object) -> int:
    """How many redirects may be followed; zero or less follows none."""
    if isinstance(value, int):
        return max(0, value)

    return 0
