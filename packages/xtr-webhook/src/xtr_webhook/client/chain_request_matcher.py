"""A matcher that claims a request only when every matcher it holds does."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ChainRequestMatcher"]


@final
class ChainRequestMatcher(RequestMatcherInterface):
    """Claims a request only when every matcher it chains claims it.

    A parser usually constrains more than one thing about what it will read — a
    ``POST``, carrying JSON — and this is how those are said together without
    each matcher learning about the others.

    A chain of nothing claims every request. Nothing constrains it, so there is
    nothing for it to refuse; a parser that reads anything says so by chaining
    no matcher rather than by leaving the hook unimplemented.
    """

    __slots__ = ("_matchers",)

    def __init__(self, matchers: Sequence[RequestMatcherInterface]) -> None:
        """Record the matchers that must all claim a request.

        Args:
            matchers: The matchers to chain. Copied, so a sequence the caller
                goes on to change cannot alter what this chain claims.
        """
        self._matchers: tuple[RequestMatcherInterface, ...] = tuple(matchers)

    @override
    def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether every chained matcher claims ``request``."""
        return all(matcher.matches(request) for matcher in self._matchers)
