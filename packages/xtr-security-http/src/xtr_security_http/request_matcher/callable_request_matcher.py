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

    The escape hatch a firewall uses when the path, host and method matchers
    do not express its claim — the callable reads the request message on its
    own, and the message's attributes carry what a handler derived of it, a
    route's path parameters among them.
    """

    __slots__ = ("_decide",)

    def __init__(self, decide: Callable[[ServerRequestInterface], bool]) -> None:
        """Record the callable that decides the claim."""
        self._decide = decide

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the callable claims ``request``."""
        return self._decide(request)
