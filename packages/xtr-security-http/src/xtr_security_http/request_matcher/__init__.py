"""The callable escape hatch among the request matchers a firewall matches with.

The matchers themselves — the path, host, method, address and chain — come
from `xtr-http-foundation`; this package keeps the callable one, which defers
a claim to whatever a firewall wants to ask of a request message.
"""

from __future__ import annotations

from .callable_request_matcher import CallableRequestMatcher

__all__ = ["CallableRequestMatcher"]
