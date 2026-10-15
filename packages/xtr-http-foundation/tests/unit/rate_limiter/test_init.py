"""The request rate limiters are reachable from the folder that groups them and from the package."""

from __future__ import annotations

import xtr_http_foundation
from xtr_http_foundation import rate_limiter

_MEMBERS = (
    "AbstractRequestRateLimiter",
    "PeekableRequestRateLimiterInterface",
    "RateLimiterInterface",
    "RequestRateLimiterInterface",
    "RequestRateLimitInterface",
)


def test_the_folder_exports_every_member() -> None:
    assert sorted(rate_limiter.__all__) == sorted(_MEMBERS)


def test_the_package_exports_the_same_members() -> None:
    for name in _MEMBERS:
        assert getattr(xtr_http_foundation, name) is getattr(rate_limiter, name)
