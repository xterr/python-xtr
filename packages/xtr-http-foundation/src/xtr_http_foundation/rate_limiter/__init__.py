"""One limit over whole requests, keyed by whatever the request itself says."""

from __future__ import annotations

from .abstract_request_rate_limiter import AbstractRequestRateLimiter
from .peekable_request_rate_limiter_interface import PeekableRequestRateLimiterInterface
from .rate_limiter_interface import RateLimiterInterface
from .request_rate_limit_interface import RequestRateLimitInterface
from .request_rate_limiter_interface import RequestRateLimiterInterface

__all__ = [
    "AbstractRequestRateLimiter",
    "PeekableRequestRateLimiterInterface",
    "RateLimiterInterface",
    "RequestRateLimitInterface",
    "RequestRateLimiterInterface",
]
