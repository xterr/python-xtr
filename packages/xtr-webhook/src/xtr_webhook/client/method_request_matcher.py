"""A matcher that claims a request by the method it arrived with."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["MethodRequestMatcher"]


@final
class MethodRequestMatcher(RequestMatcherInterface):
    """Claims a request whose method is one of those it was given.

    A sender that posts its webhooks has no business reaching the parser with a
    ``GET``, and a crawler that finds the endpoint is turned away here rather
    than after a signature check has been attempted over an empty body.

    The comparison ignores case on both sides. Methods are upper-case by
    convention and not by rule, so a sender that writes ``post`` is still the
    sender this matcher was configured for.
    """

    __slots__ = ("_methods",)

    def __init__(self, *methods: str) -> None:
        """Record the methods to claim.

        Args:
            *methods: The methods, in any case. Given none, this matcher claims
                nothing — an endpoint open to no method at all is a
                misconfiguration worth seeing as a refusal rather than being
                quietly read as "any".
        """
        self._methods: frozenset[str] = frozenset(method.upper() for method in methods)

    @override
    def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the method the request arrived with is one of the claimed ones."""
        return request.get_method().upper() in self._methods
