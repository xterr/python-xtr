"""A request limiter that can look ahead without spending anything."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .request_rate_limiter_interface import RequestRateLimiterInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from .request_rate_limit_interface import RequestRateLimitInterface

__all__ = ["PeekableRequestRateLimiterInterface"]


@runtime_checkable
class PeekableRequestRateLimiterInterface(RequestRateLimiterInterface, Protocol):
    """A request limiter that reports its limit without counting against it.

    Worth its own member where most requests will pass and only the
    failures should count — a login form, where the attempt is counted only
    when it fails. Looking ahead answers from the one place the count lives,
    and counting only on the failure keeps it that way, where consuming on
    every request and undoing the count on success would go there twice.
    """

    async def peek(self, request: ServerRequestInterface) -> RequestRateLimitInterface:
        """Report the limit ``request`` counts under, without counting it.

        Args:
            request: The request that arrived.

        Returns:
            The state of the limit as it stands, this request not counted.
        """
        ...
