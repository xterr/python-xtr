"""A limit over whole requests, keyed by whatever the request itself says."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from .request_rate_limit_interface import RequestRateLimitInterface

__all__ = ["RequestRateLimiterInterface"]


@runtime_checkable
class RequestRateLimiterInterface(Protocol):
    """Limits requests by what they are and who sent them, not by one key handed to it.

    A plain limiter counts the hits of a key it is given; a request limiter
    reads the request and decides what to count — the address it came from,
    the account it names, both at once — so the rule about which requests
    share a limit is a value the caller configures rather than a key the
    caller computes. That is also why it is awaited: the count lives where
    the hits were counted, a store shared by every server counting them.
    """

    async def consume(self, request: ServerRequestInterface) -> RequestRateLimitInterface:
        """Count ``request`` against its limit.

        Args:
            request: The request that arrived.

        Returns:
            The state of the limit as counting this request left it.
        """
        ...

    async def reset(self, request: ServerRequestInterface) -> None:
        """Forget every hit counted for the keys this request counts under."""
        ...
