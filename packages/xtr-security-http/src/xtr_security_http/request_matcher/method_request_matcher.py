"""A request matcher that claims a request by its HTTP method."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

__all__ = ["MethodRequestMatcher"]


@final
class MethodRequestMatcher(RequestMatcherInterface):
    """Claims a request whose method is one of a set, case-insensitively."""

    __slots__ = ("_methods",)

    def __init__(self, methods: Sequence[str]) -> None:
        """Record the methods to claim, upper-cased for comparison."""
        self._methods = frozenset(method.upper() for method in methods)

    @override
    def matches(self, request: Request) -> bool:
        """Tell whether the request method is one of the claimed methods."""
        return request.method.upper() in self._methods
