"""A request matcher that defers the decision to a callable."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request

__all__ = ["CallableRequestMatcher"]


@final
class CallableRequestMatcher(RequestMatcherInterface):
    """Claims a request when a callable says so.

    The escape hatch a firewall uses when path, host and method do not express
    its claim — the callable reads the request on its own and may reach into the
    route template through ``request.scope["route"]``.
    """

    __slots__ = ("_decide",)

    def __init__(self, decide: Callable[[Request], bool]) -> None:
        """Record the callable that decides the claim."""
        self._decide = decide

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the callable claims ``request``."""
        return self._decide(request)
