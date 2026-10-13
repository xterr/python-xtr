"""A matcher that claims a request only when every matcher it holds does."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ChainRequestMatcher"]


@final
class ChainRequestMatcher(RequestMatcherInterface):
    """Claims a request only when every matcher it chains claims it.

    What a piece of code will look at is usually more than one thing — a
    ``POST``, carrying JSON, from inside this network — and this is how those
    are said together without any matcher learning about the others.

    A chain of nothing claims every request: nothing constrains it, so there is
    nothing for it to refuse.
    """

    __slots__ = ("_matchers",)

    def __init__(self, matchers: Iterable[RequestMatcherInterface]) -> None:
        """Record the matchers that must all claim a request.

        Args:
            matchers: The matchers to chain. Read once and kept, so a chain
                built over a generator answers the same on every request, and
                a sequence the caller goes on to change cannot alter what the
                chain claims.
        """
        self._matchers: tuple[RequestMatcherInterface, ...] = tuple(matchers)

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether every chained matcher claims ``request``.

        The first refusal is the answer, so a matcher that reads the body is
        never asked for a request an earlier one already turned away.
        """
        for matcher in self._matchers:
            if not await matcher.matches(request):
                return False

        return True
