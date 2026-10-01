"""A request matcher that claims a request by its client address."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

__all__ = ["IpRequestMatcher"]


@final
class IpRequestMatcher(RequestMatcherInterface):
    """Claims a request whose client address is one of a set.

    A request with no known client address is never claimed — an address
    constraint the transport cannot answer is treated as unmet, not waived.
    """

    __slots__ = ("_ips",)

    def __init__(self, ips: Sequence[str]) -> None:
        """Record the client addresses to claim."""
        self._ips = frozenset(ips)

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the request's client address is one of the claimed ones."""
        client = request.client
        return client is not None and client.host in self._ips
