"""A matcher over the method of a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._comma_separated import comma_separated

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["MethodRequestMatcher"]


@final
class MethodRequestMatcher(RequestMatcherInterface):
    """Claims a request whose method is one of those named.

    The names are read in upper case, since that is the case every method is
    registered under, so a matcher may be configured in whichever case reads
    best. The request's own method is compared as it arrived: a method is
    case-sensitive on the wire, and ``get`` is not ``GET``.

    A matcher naming no method at all claims every request: it constrains
    nothing.
    """

    __slots__ = ("_methods",)

    def __init__(self, methods: Sequence[str] | str) -> None:
        """Record the methods a request may use.

        Args:
            methods: One method or several; any of them may hold a
                comma-separated list of methods.
        """
        self._methods = tuple(method.upper() for method in comma_separated(methods))

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the method of ``request`` is one this matcher names."""
        if not self._methods:
            return True

        return request.get_method() in self._methods
