"""A request matcher that claims a request only when every part does."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

__all__ = ["ChainRequestMatcher"]


@final
class ChainRequestMatcher(RequestMatcherInterface):
    """Claims a request only when every matcher it chains claims it.

    An empty chain claims every request — nothing constrains it — the way a
    rule with only a path becomes a chain of one, and a rule with no
    constraints at all matches anything.
    """

    __slots__ = ("_matchers",)

    def __init__(self, matchers: Sequence[RequestMatcherInterface]) -> None:
        """Record the matchers that must all claim a request."""
        self._matchers = tuple(matchers)

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether every chained matcher claims ``request``."""
        return all(matcher.matches(request) for matcher in self._matchers)
