"""A matcher over the headers a request carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._comma_separated import comma_separated

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["HeaderRequestMatcher"]


@final
class HeaderRequestMatcher(RequestMatcherInterface):
    """Claims a request carrying every header named, whatever each one says.

    Only their presence is asked about: this is the rule for "a request a
    gateway of ours has been through", where the header that proves it is there
    or is not, and what it holds is somebody else's business.

    Names are matched the way HTTP matches them, without regard to case. A
    matcher naming no header at all claims every request: it constrains nothing.
    """

    __slots__ = ("_headers",)

    def __init__(self, headers: Sequence[str] | str) -> None:
        """Record the header names a request has to carry.

        Args:
            headers: One name or several; any of them may hold a
                comma-separated list of names.
        """
        self._headers = comma_separated(headers)

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether ``request`` carries every header this matcher names."""
        if not self._headers:
            return True

        return all(request.has_header(header) for header in self._headers)
