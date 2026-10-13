"""A matcher over the scheme of a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._comma_separated import comma_separated

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["SchemeRequestMatcher"]


@final
class SchemeRequestMatcher(RequestMatcherInterface):
    """Claims a request made over one of the schemes named.

    This is the rule for "only over a connection nobody can read" —
    ``SchemeRequestMatcher("https")`` — which is how a firewall says that a
    credential must never travel in the clear.

    The names are read in lower case, as a scheme is matched.

    A matcher naming no scheme at all claims every request: it constrains
    nothing.
    """

    __slots__ = ("_schemes",)

    def __init__(self, schemes: Sequence[str] | str) -> None:
        """Record the schemes a request may be made over.

        Args:
            schemes: One scheme or several; any of them may hold a
                comma-separated list of schemes.
        """
        self._schemes = tuple(scheme.lower() for scheme in comma_separated(schemes))

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the scheme of ``request`` is one this matcher names."""
        if not self._schemes:
            return True

        return request.get_uri().get_scheme() in self._schemes
