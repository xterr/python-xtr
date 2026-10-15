"""The request surface an incoming HTTP request is matched and measured against.

A matcher answers one question about a request that arrived — its method, path, host, port,
scheme, a header, a query parameter, an attribute, the address it came from, whether its body
is JSON, or whatever a callable reads of it — and a chain of them answers the whole of it, so
what a piece of code claims is a value it can be handed rather than a condition written into
it.

Beside them are the address helpers those questions are built on: whether an IP falls inside a
network, and whether it is one only this network can reach.

A request is also measured: a request rate limiter counts it under the limits its own content
names — the account it carries, the address it came from — and answers with the strictest of
them, without this library prescribing where the count is kept. And a response is helped
along too, with the header value that sets a cookie on the client, or clears one.
"""

from __future__ import annotations

from .chain_request_matcher import ChainRequestMatcher
from .ip_utils import IpUtils
from .rate_limiter import (
    AbstractRequestRateLimiter,
    PeekableRequestRateLimiterInterface,
    RateLimiterInterface,
    RequestRateLimiterInterface,
    RequestRateLimitInterface,
)
from .request_matcher import (
    AttributesRequestMatcher,
    CallableRequestMatcher,
    HeaderRequestMatcher,
    HostRequestMatcher,
    IpsRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
    PortRequestMatcher,
    QueryParameterRequestMatcher,
    SchemeRequestMatcher,
)
from .request_matcher_interface import RequestMatcherInterface
from .response_cookie import cleared_cookie_header_value, cookie_header_value

__all__ = [
    "AbstractRequestRateLimiter",
    "AttributesRequestMatcher",
    "CallableRequestMatcher",
    "ChainRequestMatcher",
    "HeaderRequestMatcher",
    "HostRequestMatcher",
    "IpUtils",
    "IpsRequestMatcher",
    "IsJsonRequestMatcher",
    "MethodRequestMatcher",
    "PathRequestMatcher",
    "PeekableRequestRateLimiterInterface",
    "PortRequestMatcher",
    "QueryParameterRequestMatcher",
    "RateLimiterInterface",
    "RequestMatcherInterface",
    "RequestRateLimitInterface",
    "RequestRateLimiterInterface",
    "SchemeRequestMatcher",
    "cleared_cookie_header_value",
    "cookie_header_value",
]
