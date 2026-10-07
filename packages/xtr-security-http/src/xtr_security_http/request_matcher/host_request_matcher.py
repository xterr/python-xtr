"""A request matcher that claims a request by its host."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._pattern import compile_pattern
from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from re import Pattern

    from starlette.requests import Request

__all__ = ["HostRequestMatcher"]


@final
class HostRequestMatcher(RequestMatcherInterface):
    r"""Claims a request whose host matches a regular expression.

    A request that carries no host is never claimed — a host constraint the
    transport cannot answer is treated as unmet, not waived, consistent with
    :class:`~xtr_security_http.request_matcher.ip_request_matcher.IpRequestMatcher`.
    Like a path pattern, the host pattern is searched, not anchored; anchor it
    (``^api\\.example\\.com$``) to avoid an over-match.

    The pattern is matched against the host name alone; any port the request
    carries is ignored, so ``api\\.example\\.com`` claims a request to
    ``api.example.com:8443`` as readily as one to the default port. Match on a
    port with a :class:`~xtr_security_http.request_matcher.path_request_matcher`
    or a callable matcher if a firewall must turn on one.
    """

    __slots__ = ("_pattern",)

    def __init__(self, pattern: str) -> None:
        """Compile ``pattern`` as the host expression to match.

        Raises:
            InvalidArgumentError: When ``pattern`` will not compile.
        """
        self._pattern: Pattern[str] = compile_pattern(pattern, "host")

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the request carries a host that matches the pattern."""
        host = request.url.hostname
        return host is not None and self._pattern.search(host) is not None
