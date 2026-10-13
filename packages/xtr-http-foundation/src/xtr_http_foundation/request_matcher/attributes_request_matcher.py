"""A matcher over what handling a request has already recorded on it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

from ._compiled_regexp import compiled_regexp

if TYPE_CHECKING:
    import re
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AttributesRequestMatcher"]


@final
class AttributesRequestMatcher(RequestMatcherInterface):
    """Claims a request whose attributes all match the expressions named for them.

    An attribute is what handling the request worked out about it — the named
    parameters a path matched, the user an authorization header resolved to — so
    this matcher is how a rule is written about a finding rather than about the
    request as it arrived.

    An attribute that is not text is never claimed: there is nothing to match an
    expression against, and neither is one the request does not carry at all.
    """

    __slots__ = ("_regexps",)

    def __init__(self, regexps: Mapping[str, str]) -> None:
        """Record one expression per attribute, all of which must match.

        Args:
            regexps: Each attribute name mapped to the expression its value has
                to match. Read when the matcher is built.

        Raises:
            InvalidArgumentError: When one of the expressions does not read as
                one; it names the expression.
        """
        self._regexps: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
            (name, compiled_regexp(regexp)) for name, regexp in regexps.items()
        )

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether every named attribute of ``request`` matches its expression."""
        for name, regexp in self._regexps:
            attribute = request.get_attribute(name)
            if not isinstance(attribute, str):
                return False
            if regexp.search(attribute) is None:
                return False

        return True
