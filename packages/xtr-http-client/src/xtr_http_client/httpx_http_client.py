"""The client that opens the connections and streams what comes back."""

from __future__ import annotations

import time
from collections.abc import AsyncIterable, Mapping, Sequence
from typing import TYPE_CHECKING, Final, NamedTuple, cast, final

import anyio
import httpx
from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_message import Request

from .exception import InvalidArgumentError, TransportError
from .http_client_mixin import HttpClientMixin
from .internal.debug_type import debug_type
from .internal.httpx_clients import HttpxClients
from .internal.httpx_errors import timed_out, transport_error
from .internal.httpx_redirect import next_hop, same_origin
from .response.httpx_response import to_http_response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType
    from typing import Self

    from xtr_http_client_contracts import RequestOptions
    from xtr_http_message_contracts import RequestInterface

    from .response import HttpResponse

__all__ = ["HttpxHttpClient"]

# Quoted by the contract rather than described, so it is written out once and
# never composed.
_BOTH_BODIES: Final = (
    'Define either the request body or the "body" or "json" option, setting both is not supported.'
)

# What a body of bytes, text or pieces is taken to be when nobody said: the
# only shape a request body has without a content type to read it by.
_FORM: Final = "application/x-www-form-urlencoded"

_NO_BODY: Final = (None, b"", "")


class _Payload(NamedTuple):
    """The one body of a request, in whichever of three shapes it is to be sent."""

    content: bytes | str | AsyncIterator[bytes] | None
    form: Mapping[str, object] | None
    document: object


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
        headers = _headers(request, merged)
        payload = await _payload(request, merged, headers)
        url, extensions = _pinned(_target(request, merged), merged, resolved, headers)

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
            decode=not _carries(headers, "accept-encoding"),
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


def _target(request: RequestInterface, options: Mapping[str, object]) -> httpx.URL:
    """The URL to request: the request's own, resolved and with ``query`` merged in."""
    url = httpx.URL(str(request.get_uri()))

    base = options.get("base_uri")
    if url.is_relative_url and base is not None:
        url = httpx.URL(_base_uri(base)).join(url)

    query = options.get("query")
    if query:
        url = url.copy_merge_params(cast("Mapping[str, str]", query))

    return url


def _base_uri(base: object) -> str:
    """The URI a relative URL is resolved against.

    A sequence of them is for a client that retries, which moves along it
    from one attempt to the next; this one makes a single attempt, so it
    resolves against the first.
    """
    if isinstance(base, str):
        return base
    if isinstance(base, Sequence) and base:
        first = base[0]
        if isinstance(first, str):
            return first

    raise InvalidArgumentError(
        f'Option "base_uri" must be a URL or a list of them, "{debug_type(base)}" given.'
    )


def _headers(
    request: RequestInterface,
    options: Mapping[str, object],
) -> list[tuple[str, str]]:
    """Every header to send: the request's, then the names it left out.

    The ``Host`` the request worked out from its own URI is dropped, because
    the URL actually requested may not be that one — a relative URI resolved
    against a base, or a host pinned to an address, both move it — and a
    header nobody asked for must not be the one that decides where a request
    lands. One the caller set by hand is kept and sent exactly as given.
    """
    headers = [
        (name, value)
        for name, values in request.get_headers().items()
        for value in values
        if not _is_implied_host(name, value, request)
    ]

    for name, value in _mapping(options.get("headers")).items():
        if _carries(headers, name):
            continue
        headers += _values(name, value)

    bearer = options.get("auth_bearer")
    if isinstance(bearer, str) and bearer and not _carries(headers, "authorization"):
        headers.append(("Authorization", f"Bearer {bearer}"))

    return headers


def _is_implied_host(name: str, value: str, request: RequestInterface) -> bool:
    """Whether a header is the ``Host`` a request filled in from its own URI."""
    if name.lower() != "host":
        return False

    uri = request.get_uri()
    host = uri.get_host()
    port = uri.get_port()

    return value == (host if port is None else f"{host}:{port}")


async def _payload(
    request: RequestInterface,
    options: Mapping[str, object],
    headers: list[tuple[str, str]],
) -> _Payload:
    """What to send as the body, from the request or from the options, never both.

    A request carrying a body has already said what to send, so a ``body`` or
    ``json`` option alongside it is two answers to one question and is
    refused rather than one of them being picked.

    Raises:
        InvalidArgumentError: When the request carries a body and an option
            gives another.
    """
    carried = await request.get_body().get_contents()
    if carried:
        if options.get("body") not in _NO_BODY or options.get("json") is not None:
            raise InvalidArgumentError(_BOTH_BODIES)
        _imply_form(headers)

        return _Payload(carried, None, None)

    return _asked_for(options, headers)


def _asked_for(options: Mapping[str, object], headers: list[tuple[str, str]]) -> _Payload:
    """What the options alone say to send, for a request that carried no body.

    A mapping is a form, which the backend writes out; bytes, text and an
    iterable are a body nobody labelled, so they are said to be a form here;
    and a JSON document labels itself.
    """
    document = options.get("json")
    if document is not None:
        return _Payload(None, None, document)

    body = options.get("body")
    if isinstance(body, Mapping):
        return _Payload(None, cast("Mapping[str, object]", body), None)
    if isinstance(body, (bytes, str)) and body:
        _imply_form(headers)

        return _Payload(body, None, None)
    if isinstance(body, AsyncIterable):
        _imply_form(headers)

        return _Payload(_checked(body), None, None)

    return _Payload(None, None, None)


async def _checked(source: AsyncIterable[object]) -> AsyncIterator[bytes]:
    """``source``, with a piece that is not bytes refused before it reaches the wire.

    Raises:
        TransportError: When the body produces anything other than bytes.
            The request fails rather than the backend tripping over it with
            an error from somewhere a caller cannot place.
    """
    async for piece in source:
        if not isinstance(piece, (bytes, bytearray)):
            raise TransportError(
                f'The request body produced "{debug_type(piece)}", which is not bytes.'
            )
        yield bytes(piece)


def _pinned(
    url: httpx.URL,
    options: Mapping[str, object],
    resolved: dict[str, str],
    headers: list[tuple[str, str]],
) -> tuple[httpx.URL, dict[str, str]]:
    """The URL to connect to, with the host swapped for the address it is pinned to.

    Pinning is what makes a request reach an address that has already been
    checked, so nothing can change under it between the check and the
    connection. The host survives the swap in two places that still need it:
    the ``Host`` header, which is what the server routes on, and the name the
    TLS handshake asks for.
    """
    resolved.update(_text_mapping(options.get("resolve")))

    host = url.raw_host.decode("ascii")
    address = resolved.get(host)
    if address is None:
        return url, {}

    _replace(headers, "Host", host if url.port is None else f"{host}:{url.port}")

    return url.copy_with(host=address), {"sni_hostname": host}


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
    if basic is None or _carries(headers, "authorization"):
        return None

    if isinstance(basic, str):
        user, _, password = basic.partition(":")

        return user, password

    parts = [str(part) for part in cast("Sequence[object]", basic)]

    return parts[0], parts[1] if len(parts) > 1 else ""


def _carries(headers: Sequence[tuple[str, str]], name: str) -> bool:
    """Whether a header of that name is already there, matched without case."""
    wanted = name.lower()

    return any(present.lower() == wanted for present, _ in headers)


def _replace(headers: list[tuple[str, str]], name: str, value: str) -> None:
    """Make ``name`` hold ``value`` and nothing else."""
    wanted = name.lower()
    headers[:] = [entry for entry in headers if entry[0].lower() != wanted]
    headers.append((name, value))


def _imply_form(headers: list[tuple[str, str]]) -> None:
    """Say what an unlabelled body is, since a server cannot read one unlabelled."""
    if not _carries(headers, "content-type"):
        headers.append(("Content-Type", _FORM))


def _values(name: str, value: object) -> list[tuple[str, str]]:
    """One header name and every value given for it."""
    if isinstance(value, str):
        return [(name, value)]
    if isinstance(value, Sequence):
        return [(name, str(one)) for one in value]

    raise InvalidArgumentError(
        f'Option "headers" must map a name to a string or a list of them, '
        f'"{debug_type(value)}" given for "{name}".'
    )


def _mapping(value: object) -> Mapping[str, object]:
    """``value`` as a mapping, or an empty one when it was left out."""
    if isinstance(value, Mapping):
        return cast("Mapping[str, object]", value)

    return {}


def _text_mapping(value: object) -> dict[str, str]:
    """``value`` as a mapping of text to text, keeping only the entries that are."""
    return {name: entry for name, entry in _mapping(value).items() if isinstance(entry, str)}


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
