"""The client that refuses to reach an address only this network can see."""

from __future__ import annotations

import socket
from collections.abc import Mapping
from io import BytesIO
from ipaddress import ip_address
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urljoin

import anyio
from typing_extensions import Unpack, override
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_foundation import IpUtils
from xtr_http_message import Request, Stream, Uri
from xtr_service_contracts import ResetInterface

from .exception import InvalidArgumentError, TransportError
from .internal.option_merge import as_options

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from typing import Self

    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions
    from xtr_http_message_contracts import RequestInterface

__all__ = ["NoPrivateNetworkHttpClient"]

_PORTS: Final[Mapping[str, int]] = {"http": 80, "https": 443}
_REDIRECT: Final = range(300, 400)
_TO_GET: Final = (301, 302)
_SEE_OTHER: Final = 303
_HOPS: Final = 20
_BODY: Final = ("body", "json")


@final
class NoPrivateNetworkHttpClient(HttpClientInterface, ResetInterface):
    """Wraps a client and refuses every request that leads inwards.

    A URL that came from outside is data, so without this a request is a way
    to make this process reach an address only this process can see: another
    service on the same network, an admin port, a metadata endpoint handing
    out credentials.

    ```python
    client = NoPrivateNetworkHttpClient(inner)
    response = await client.request("GET", "https://example.com/avatar")
    ```

    The check runs on what the host *resolves to*, not on how it is written,
    and one refused address refuses the whole request — whichever of them the
    connection would pick, nothing is sent. The request is then pinned to the
    address that was checked, through the ``resolve`` option, so a name whose
    records change between the check and the connection reaches what was
    vetted or nothing at all.

    Redirects are followed here rather than by the wrapped client, because a
    hop nobody checked would walk straight past the guard: each one is
    resolved and checked like the request that started the chain.

    What a host resolves to is remembered for as long as this client lives,
    so a chain of hops back to the same host asks the resolver once;
    :meth:`reset` forgets it.
    """

    __slots__ = ("_allow_list", "_client", "_dns_cache", "_resolver", "_subnets")

    def __init__(
        self,
        client: HttpClientInterface,
        subnets: str | Sequence[str] | None = None,
        allow_list: str | Sequence[str] = (),
        resolver: Callable[[str, int], Awaitable[Sequence[str]]] | None = None,
    ) -> None:
        """Guard ``client``, refusing whichever networks ``subnets`` names.

        Args:
            client: The client every vetted request is handed to.
            subnets: The networks to refuse, in CIDR notation or as single
                addresses, replacing the default. ``None`` refuses the
                networks only this one can reach.
            allow_list: Networks or addresses exempt from the refusal, which
                is how one internal receiver is opened without opening the
                network it sits in. Addresses only, never host names: the
                check runs on resolved addresses, and a name would itself
                have to be resolved, and could point anywhere by then.
            resolver: What every address of a host and port is asked of.
                ``None`` asks the platform's own resolver.
        """
        self._client = client
        self._subnets = _entries(subnets) if subnets is not None else IpUtils.PRIVATE_SUBNETS
        self._allow_list = _entries(allow_list)
        self._resolver = resolver if resolver is not None else _getaddrinfo
        self._dns_cache: dict[str, Sequence[str]] = {}

    @override
    async def request(
        self,
        method: str,
        url: str,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Make a request for ``method`` and ``url``, once where it leads is vetted.

        Args:
            method: The HTTP method, in upper case.
            url: The URL to request, absolute or relative to ``base_uri``.
            **options: How the request is to be made.

        Returns:
            Whatever the wrapped client answers at the end of the chain.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option.
            TransportError: When the host is, or resolves to, a refused
                address, and when no answer came.
        """
        return await self.send_request(Request(method, url), **options)

    @override
    async def send_request(
        self,
        request: RequestInterface,
        **options: Unpack[RequestOptions],
    ) -> HttpResponseInterface:
        """Send ``request``, vetting every host the chain reaches.

        Args:
            request: The request to send.
            **options: What the request leaves out.

        Returns:
            Whatever the wrapped client answers at the end of the chain.

        Raises:
            InvalidArgumentError: For an invalid method, URL or option, and
                for a URL that is relative with no ``base_uri`` to resolve it.
            TransportError: When a host is, or resolves to, a refused
                address, and when no answer came.
        """
        allowed = _hops(options.get("max_redirects"))
        given: dict[str, object] = dict(options)
        outgoing = _absolute(request, given.get("base_uri"))
        hops = 0

        while True:
            response = await self._sent(outgoing, given)
            following = _next_hop(outgoing, response) if hops < allowed else None
            if following is None:
                return response

            await response.cancel()
            if following.get_method() != outgoing.get_method():
                given = {name: value for name, value in given.items() if name not in _BODY}
            outgoing = following
            hops += 1

    @override
    def with_options(self, **options: Unpack[RequestOptions]) -> Self:
        """Return a copy around a wrapped client whose defaults have ``options`` over them.

        Args:
            **options: The defaults of the wrapped client of the copy.

        Returns:
            A new client, guarding the same networks and sharing this one's
            address cache, so a host resolved through either is known to both.

        Raises:
            InvalidArgumentError: When an option is invalid.
        """
        narrowed = type(self)(
            self._client.with_options(**options),
            self._subnets,
            self._allow_list,
            self._resolver,
        )
        narrowed._dns_cache = self._dns_cache  # noqa: SLF001 — same class, same cache by design

        return narrowed

    @override
    def reset(self) -> None:
        """Forget what every host resolved to, and reset the wrapped client."""
        self._dns_cache.clear()

        if isinstance(self._client, ResetInterface):
            self._client.reset()

    async def _sent(
        self,
        outgoing: RequestInterface,
        options: Mapping[str, object],
    ) -> HttpResponseInterface:
        """Hand one hop to the wrapped client, pinned to the address it was vetted at."""
        uri = outgoing.get_uri()
        host = uri.get_host()
        url = str(uri)
        port = uri.get_port() or _PORTS.get(uri.get_scheme(), 0)
        address = await self._vetted(host, port, options.get("resolve"), url)

        sent: Mapping[str, object] = {
            **options,
            # Zero hops, because the chain is walked here: a hop the wrapped
            # client followed on its own would reach a host nobody checked.
            "max_redirects": 0,
            "resolve": {**_text_mapping(options.get("resolve")), host: address},
        }

        return await self._client.send_request(outgoing, **as_options(sent))

    async def _vetted(self, host: str, port: int, pinned: object, url: str) -> str:
        """The address this request may go to, every one of the host's having passed.

        Raises:
            TransportError: When any address the host has is refused, since
                whichever one the connection would pick is one of them.
        """
        literal = _literal(host)
        if literal is not None:
            addresses: Sequence[str] = (literal,)
        else:
            named = _text_mapping(pinned).get(host)
            addresses = (named,) if named else await self._addresses(host, port, url)

        for address in addresses:
            if self._refuses(address):
                blocked = f'IP "{address}"' if literal is not None else f'Host "{host}"'
                raise TransportError(f'{blocked} is blocked for "{url}".')

        return addresses[0]

    async def _addresses(self, host: str, port: int, url: str) -> Sequence[str]:
        """Every address ``host`` has, asked once and remembered.

        Raises:
            TransportError: When the host has no address at all, which is a
                request that can reach nothing rather than one to send.
        """
        cached = self._dns_cache.get(host)
        if cached is not None:
            return cached

        resolved = tuple(await self._resolver(host, port))
        if not resolved:
            raise TransportError(f'Host "{host}" could not be resolved for "{url}".')

        self._dns_cache[host] = resolved

        return resolved

    def _refuses(self, address: str) -> bool:
        """Whether ``address`` may not be connected to.

        The allow list is read first, so one internal receiver is opened
        without opening the network it sits in.
        """
        if self._allow_list and IpUtils.check_ip(address, self._allow_list):
            return False

        return IpUtils.check_ip(address, self._subnets)


async def _getaddrinfo(host: str, port: int) -> Sequence[str]:
    """Every address the platform's resolver gives for ``host`` at ``port``."""
    resolved = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    return [str(sockaddr[0]) for *_, sockaddr in resolved]


def _absolute(request: RequestInterface, base: object) -> RequestInterface:
    """``request`` carrying a URL with a host in it, resolved against ``base``.

    Raises:
        InvalidArgumentError: When nothing says which host the request is
            for, since there is then no address to check.
    """
    if not request.get_uri().get_host() and isinstance(base, str):
        request = request.with_uri(Uri(urljoin(base, str(request.get_uri()))))

    if not request.get_uri().get_host():
        raise InvalidArgumentError(
            f'Invalid URL "{request.get_uri()}": it names no host, so there is '
            "no address to check it against."
        )

    return request


def _next_hop(
    outgoing: RequestInterface, response: HttpResponseInterface
) -> RequestInterface | None:
    """Where the answer points, or ``None`` when it points nowhere."""
    status = response.get_status_code()
    location = response.get_header_line("location")
    if status not in _REDIRECT or not location:
        return None

    following = outgoing.with_uri(Uri(urljoin(str(outgoing.get_uri()), location)))
    if status == _SEE_OTHER or (status in _TO_GET and following.get_method() == "POST"):
        # What the body was sent to say has been answered; carrying it on
        # would say it again, to a resource that was never offered it.
        return following.with_method("GET").with_body(Stream(BytesIO(b"")))

    return following


def _literal(host: str) -> str | None:
    """The address ``host`` writes out, or ``None`` when it is a name."""
    text = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        return str(ip_address(text))
    except ValueError:
        return None


def _entries(value: str | Sequence[str]) -> tuple[str, ...]:
    """One network or several, as several."""
    return (value,) if isinstance(value, str) else tuple(value)


def _hops(value: object) -> int:
    """How many redirects may be followed; zero or less follows none."""
    if isinstance(value, int):
        return max(0, value)

    return _HOPS


def _text_mapping(value: object) -> dict[str, str]:
    """``value`` as a mapping of text to text, keeping only the entries that are."""
    if not isinstance(value, Mapping):
        return {}

    return {
        name: entry
        for name, entry in cast("Mapping[str, object]", value).items()
        if isinstance(entry, str)
    }
