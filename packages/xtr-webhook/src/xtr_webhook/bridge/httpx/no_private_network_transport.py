"""The transport that refuses to send a webhook into a private network."""

from __future__ import annotations

import ipaddress
import socket
from typing import TYPE_CHECKING, final

import anyio
import httpx
from typing_extensions import override

from xtr_webhook.exception import PrivateNetworkError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from ipaddress import IPv4Address, IPv6Address

__all__ = ["NoPrivateNetworkTransport"]

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


@final
class NoPrivateNetworkTransport(httpx.AsyncBaseTransport):
    """Wraps a transport and refuses every request that leads inwards.

    A subscriber url is data — chosen by whoever registered it — so without
    this, a webhook is a way to make this process call an address only this
    process can see. The check runs on what the host *resolves to*, not on how
    it is written, and the request is then pinned to the address that was
    checked, so a name whose records change between the check and the
    connection — a rebinding attack — connects to what was vetted or not at
    all.

    Opt-in, wrapped around the client's own transport::

        client = httpx.AsyncClient(
            transport=NoPrivateNetworkTransport(httpx.AsyncHTTPTransport()),
        )
    """

    __slots__ = ("_allow_list", "_blocked", "_inner")

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        subnets: Sequence[str] | None = None,
        allow_list: Sequence[str] = (),
    ) -> None:
        """Configure what is refused, and what carries the vetted requests.

        Args:
            inner: The transport a vetted request is handed to.
            subnets: The networks to refuse, replacing the default. ``None``
                refuses every address that is not globally routable — loopback,
                private, link-local, carrier-grade NAT, unique-local,
                multicast, reserved and unspecified alike.
            allow_list: Networks or single addresses exempt from the refusal.
                Addresses only, never hostnames: the check runs on resolved
                addresses, and a name would itself have to be resolved —
                and could point anywhere by then.

        Raises:
            ValueError: When a subnet or allow-list entry is not an IP network
                or address.
        """
        self._inner = inner
        self._blocked = (
            None
            if subnets is None
            else tuple(ipaddress.ip_network(subnet, strict=False) for subnet in subnets)
        )
        self._allow_list = tuple(ipaddress.ip_network(entry, strict=False) for entry in allow_list)

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Vet where ``request`` leads, then hand it on — or refuse it.

        Args:
            request: The outgoing request, exactly as the client built it.

        Returns:
            Whatever the inner transport answers.

        Raises:
            PrivateNetworkError: When the host is, or resolves to, a refused
                address. One refused address refuses the whole delivery —
                whichever of its addresses the connection would pick, nothing
                is sent.
        """
        host = request.url.host

        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None

        if literal is not None:
            if self._refuses(literal):
                raise PrivateNetworkError(host, str(literal))

            return await self._inner.handle_async_request(request)

        addresses = await self._resolve(host, request.url)
        for address in addresses:
            if self._refuses(address):
                raise PrivateNetworkError(host, str(address))

        # Pin the connection to the first vetted address by rewriting the url's
        # host to it (copy_with brackets an IPv6 address), keeping the Host
        # header the request already carries. Pinning one address is safe only
        # because redirects are never followed (HttpxSender posts with
        # follow_redirects=False) and any 3xx raises (Transport refuses every
        # answer outside 2xx), so a receiver cannot bounce the request past the
        # check. Certificate verification still checks the original host name:
        # httpcore honours the sni_hostname extension
        # (httpcore/_async/connection.py), so the IP in the url decides only
        # where the connection goes.
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=str(addresses[0])),
            headers=request.headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": host},
        )

        return await self._inner.handle_async_request(pinned)

    @override
    async def aclose(self) -> None:
        """Close the inner transport; this one holds nothing of its own."""
        await self._inner.aclose()

    async def _resolve(self, host: str, url: httpx.URL) -> list[IPv4Address | IPv6Address]:
        """Resolve ``host`` without blocking the event loop.

        The port matters only to the resolver's filtering; the addresses are
        what the check and the pin need.
        """
        port = url.port or _DEFAULT_PORTS.get(url.scheme, 0)
        resolved = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)

        return [ipaddress.ip_address(sockaddr[0]) for *_, sockaddr in resolved]

    def _refuses(self, address: IPv4Address | IPv6Address) -> bool:
        """Whether ``address`` may not be connected to.

        The allow list is read first, so an application can open one internal
        receiver without opening the network it sits in.
        """
        if any(address in allowed for allowed in self._allow_list):
            return False

        if self._blocked is None:
            return not address.is_global

        return any(address in blocked for blocked in self._blocked)
