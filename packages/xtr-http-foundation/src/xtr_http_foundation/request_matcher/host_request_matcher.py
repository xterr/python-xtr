"""A matcher over the host a request was addressed to."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._compiled_regexp import compiled_regexp

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["HostRequestMatcher"]


@final
class HostRequestMatcher(RequestMatcherInterface):
    r"""Claims a request whose host matches an expression.

    The expression is searched for in the host rather than having to describe
    the whole of it, so ``\.example\.com$`` is the rule for a subdomain and
    ``^admin\.example\.com$`` the rule for exactly one host.

    A host names the same machine however it is written, so it is matched
    without regard to case.
    """

    __slots__ = ("_regexp",)

    def __init__(self, regexp: str) -> None:
        """Record the expression a request's host has to match.

        Args:
            regexp: The expression, read when the matcher is built.

        Raises:
            InvalidArgumentError: When it does not read as one; it names the
                expression.
        """
        self._regexp = compiled_regexp(regexp, re.IGNORECASE)

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the host of ``request`` matches this matcher's expression."""
        return self._regexp.search(request.get_uri().get_host()) is not None
