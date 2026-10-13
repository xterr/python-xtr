"""A matcher over the address a request came from."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_http_foundation.ip_utils import IpUtils
from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._comma_separated import comma_separated

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["IpsRequestMatcher"]

_CLIENT: Final = "client"
"""Where the server reports who it is talking to: the address first, then the port."""


def _client_address(request: ServerRequestInterface) -> str:
    """Return the address the server reported, or no address at all.

    Nothing about a request itself says where it came from — only the server
    that accepted it knows, and it says so among the environment parameters. A
    server that said nothing, or said something that is not an address, leaves
    the question unanswerable, which the checks below read as an address no
    network holds.
    """
    client = request.get_server_params().get(_CLIENT)
    if isinstance(client, str) or not isinstance(client, Sequence):
        return ""

    first = client[0] if client else None

    return first if isinstance(first, str) else ""


@final
class IpsRequestMatcher(RequestMatcherInterface):
    """Claims a request that came from one of the addresses or networks named.

    The address is the one the server accepted the connection from, so a request
    that travelled through a proxy comes from the proxy: a rule about the
    original caller belongs where the forwarded headers are trusted and resolved.

    A matcher naming no address at all claims every request: it constrains
    nothing.
    """

    __slots__ = ("_ips",)

    def __init__(self, ips: Sequence[str] | str) -> None:
        """Record the addresses and networks a request may come from.

        Args:
            ips: A single address, a network in CIDR notation such as
                ``192.168.1.0/24``, or several of either; any of them may hold
                a comma-separated list.
        """
        self._ips = comma_separated(ips)

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether ``request`` came from any of the addresses this matcher names."""
        if not self._ips:
            return True

        return IpUtils.check_ip(_client_address(request), self._ips)
