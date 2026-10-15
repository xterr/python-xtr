"""The counter a request limiter's answer is built from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .request_rate_limit_interface import RequestRateLimitInterface

__all__ = ["RateLimiterInterface"]


@runtime_checkable
class RateLimiterInterface(Protocol):
    """Counts the hits of one key — one user, one address, one account — against a limit.

    A request limiter reads the keys it cares about out of the request and
    hands each of them one of these, so this is the least it asks of a
    counter: spend tokens, and forget the hits counted. A counter that can
    do more — book tokens for a moment that lies ahead, say — serves as
    well, since a counter with more members still answers this shape.

    Spending zero tokens changes nothing and reports the limit as it stands,
    which is how a request limiter looks ahead without spending anything.
    """

    async def consume(self, tokens: int = 1) -> RequestRateLimitInterface:
        """Spend ``tokens`` now if they are available; spend nothing otherwise.

        Awaited because the count lives where the hits were counted — a
        store shared by every server counting them.

        Args:
            tokens: How many tokens to spend; zero to only report the limit
                as it stands.

        Returns:
            The state of the limit as the spending left it.
        """
        ...

    async def reset(self) -> None:
        """Forget every hit counted for this key."""
        ...
