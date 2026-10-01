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
    """Claims a request whose host matches a regular expression.

    A request that carries no host is claimed all the same — the host
    constraint is enforced only when there is a host to read, so a rule stays
    applicable to requests a transport leaves hostless.
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
        """Tell whether the request host matches the pattern, or is absent."""
        host = request.url.hostname
        return host is None or self._pattern.search(host) is not None
