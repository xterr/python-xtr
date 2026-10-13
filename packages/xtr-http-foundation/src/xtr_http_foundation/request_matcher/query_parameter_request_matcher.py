"""A matcher over the query parameters a request opens with."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._comma_separated import comma_separated

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["QueryParameterRequestMatcher"]


@final
class QueryParameterRequestMatcher(RequestMatcherInterface):
    """Claims a request whose query string opens with the parameters named.

    Only their presence is asked about, never their values: this is the rule for
    "a request asking the question this code answers", where a parameter being
    there is what says so.

    They are matched by position, and the first of them has to be the query's
    first parameter: a query carrying further parameters after them is claimed,
    while one missing any of them, or carrying them in another order, is not.
    The names are read in lower case, and the query's own are compared as they
    arrived — a query string is a value, and nothing says a parameter means the
    same written in another case.

    A matcher naming no parameter at all claims every request: it constrains
    nothing.
    """

    __slots__ = ("_parameters",)

    def __init__(self, parameters: Sequence[str] | str) -> None:
        """Record the query parameters a request has to open with.

        Args:
            parameters: One name or several; any of them may hold a
                comma-separated list of names.
        """
        self._parameters = tuple(name.lower() for name in comma_separated(parameters))

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the query of ``request`` opens with the parameters named."""
        if not self._parameters:
            return True

        asked = tuple(request.get_query_params())

        return asked[: len(self._parameters)] == self._parameters
