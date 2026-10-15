"""A request matcher that defers the decision to a callable."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["CallableRequestMatcher"]


@final
class CallableRequestMatcher(RequestMatcherInterface):
    """Claims a request when a callable says so.

    The escape hatch when no matcher here expresses the claim — the callable
    reads the request on its own, and the request's attributes carry what a
    handler derived of it, a route's path parameters among them. The callable
    answers as it is called, so it decides from what the request already
    carries; a claim that has to be awaited is better written as a matcher
    of its own.
    """

    __slots__ = ("_decide",)

    def __init__(self, decide: Callable[[ServerRequestInterface], bool]) -> None:
        """Record the callable that decides the claim.

        Args:
            decide: Reads the request and tells whether it is claimed. Called
                once per question, so it should decide rather than gather.
        """
        self._decide = decide

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the callable claims ``request``."""
        return self._decide(request)
