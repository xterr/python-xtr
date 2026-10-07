"""A request matcher that claims a request by its client address."""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

__all__ = ["IpRequestMatcher"]


@final
class IpRequestMatcher(RequestMatcherInterface):
    """Claims a request whose client address falls in one of a set of networks.

    Each entry is a single address (``10.0.0.1``) or a CIDR network
    (``10.0.0.0/8``); a request is claimed when its client address lies in any
    of them. A request with no known client address is never claimed — an
    address constraint the transport cannot answer is treated as unmet, not
    waived.
    """

    __slots__ = ("_networks",)

    def __init__(self, ips: Sequence[str]) -> None:
        """Parse each entry as an address or CIDR network to claim.

        Raises:
            InvalidArgumentError: When an entry is not a valid address or
                network.
        """
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for entry in ips:
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError as error:
                raise InvalidArgumentError(
                    f"The address matcher entry {entry!r} is not a valid address or network.",
                ) from error
        self._networks = tuple(networks)

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the request's client address lies in a claimed network."""
        client = request.client
        if client is None:
            return False
        try:
            address = ipaddress.ip_address(client.host)
        except ValueError:
            return False
        return any(address in network for network in self._networks)
