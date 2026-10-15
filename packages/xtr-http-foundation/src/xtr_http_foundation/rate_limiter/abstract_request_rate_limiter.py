"""The counting, the looking ahead and the forgetting most request limiters share."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .peekable_request_rate_limiter_interface import PeekableRequestRateLimiterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

    from .rate_limiter_interface import RateLimiterInterface
    from .request_rate_limit_interface import RequestRateLimitInterface

__all__ = ["AbstractRequestRateLimiter"]


class AbstractRequestRateLimiter(PeekableRequestRateLimiterInterface, ABC):
    """Counts a request under every limiter a subclass names for it.

    A request usually counts under more than one limit at once — the account
    it names and the address it came from — and the answer that matters is
    the strictest of them, because a request passes only when every limit
    passes. This holds the counting, the looking ahead and the forgetting,
    so a subclass says only which limiters a request counts under.

    A request that counts under no limiter at all is unlimited: nothing
    constrains it, so there is nothing to refuse.
    """

    @override
    async def consume(self, request: ServerRequestInterface) -> RequestRateLimitInterface:
        """Count ``request`` once against every limit it counts under."""
        return await self._consume(request, 1)

    @override
    async def peek(self, request: ServerRequestInterface) -> RequestRateLimitInterface:
        """Report every limit ``request`` counts under, without counting it."""
        return await self._consume(request, 0)

    async def _consume(
        self, request: ServerRequestInterface, tokens: int
    ) -> RequestRateLimitInterface:
        """Spend ``tokens`` in every limiter ``request`` counts under.

        The answer is the strictest limit the spending left, because a
        request passes only when every limit passes.
        """
        limiters = self.get_limiters(request)
        if not limiters:
            return _UnlimitedRateLimit()

        rate_limits = [await limiter.consume(tokens) for limiter in limiters]
        strictest = rate_limits[0]
        for rate_limit in rate_limits[1:]:
            strictest = self._strictest(strictest, rate_limit)

        return strictest

    @override
    async def reset(self, request: ServerRequestInterface) -> None:
        """Forget every hit counted for the keys ``request`` counts under."""
        for limiter in self.get_limiters(request):
            await limiter.reset()

    @abstractmethod
    def get_limiters(self, request: ServerRequestInterface) -> Sequence[RateLimiterInterface]:
        """Return the limiters ``request`` counts under.

        The keys a request counts under are read here — the address it came
        from, the account it names — because that is the one thing this shape
        cannot know. Called once per consumption and once per reset.

        Args:
            request: The request that arrived.

        Returns:
            The limiters to count under; none for a request that is
            unlimited.
        """

    @staticmethod
    def _strictest(
        first: RequestRateLimitInterface, second: RequestRateLimitInterface
    ) -> RequestRateLimitInterface:
        """Return the limit a request is less likely to pass.

        A refused limit is stricter than a granted one, whatever else it
        says; between two granted ones, the one with fewer tokens left; and
        between two with the same number left, the one that waits longer.
        """
        if first.is_accepted() != second.is_accepted():
            return second if first.is_accepted() else first

        if first.remaining_tokens == second.remaining_tokens:
            return second if first.retry_after < second.retry_after else first

        return second if first.remaining_tokens > second.remaining_tokens else first


@final
class _UnlimitedRateLimit:
    """The state of a limit that does not exist.

    A request that counts under no limiter is still owed an answer, and the
    answer is that nothing was refused and nothing is left to run out of.
    """

    __slots__ = ("_retry_after",)

    def __init__(self) -> None:
        """Read the moment the answer is given, as the one to come back at."""
        self._retry_after = datetime.now(UTC)

    def is_accepted(self) -> bool:
        """Tell whether the tokens asked for were granted."""
        return True

    @property
    def remaining_tokens(self) -> int:
        """How many tokens are left."""
        return sys.maxsize

    @property
    def retry_after(self) -> datetime:
        """When the tokens asked for become available: now, since none were asked for."""
        return self._retry_after

    @property
    def limit(self) -> int:
        """How many tokens the limiter holds when full."""
        return sys.maxsize

    @property
    def reset_at(self) -> datetime | None:
        """When the limiter holds every token again; it never stopped."""
        return None
