"""A request matcher that claims a request by its path."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._pattern import compile_pattern
from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from re import Pattern

    from starlette.requests import Request

__all__ = ["PathRequestMatcher"]


@final
class PathRequestMatcher(RequestMatcherInterface):
    """Claims a request whose path matches a regular expression.

    The pattern is searched, not anchored, so ``^/api`` claims ``/api`` and
    everything under it.
    """

    __slots__ = ("_pattern",)

    def __init__(self, pattern: str) -> None:
        """Compile ``pattern`` as the path expression to match.

        Raises:
            InvalidArgumentError: When ``pattern`` will not compile.
        """
        self._pattern: Pattern[str] = compile_pattern(pattern, "path")

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the request path matches the pattern."""
        return self._pattern.search(request.url.path) is not None
