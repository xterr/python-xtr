"""The rate limiters capping the transports, from the rate limiter bundle.

Imported only when that bundle is active.
"""

from __future__ import annotations

from xtr_dependency_injection import ServiceLocator
from xtr_rate_limiter import RateLimiterFactoryInterface

from ._peers import RateLimitersPeer

__all__ = ["rate_limiters_peer"]


def rate_limiters_peer(
    rate_limiters: ServiceLocator[RateLimiterFactoryInterface],
) -> RateLimitersPeer:
    """Hold the configured rate limiters, each built only when a transport names it."""
    return RateLimitersPeer(rate_limiters)
