"""Which incoming requests a parser is willing to look at."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["RequestMatcherInterface"]


@runtime_checkable
class RequestMatcherInterface(Protocol):
    """Answers one question about a request: is this one of mine?

    A parser states what a webhook from its sender looks like — the method, the
    media type — and the request that does not look like that is turned away
    before anything reads its body. That keeps the two concerns apart: a matcher
    never decides whether a request is authentic, and a parser never has to
    re-check the shape of what it was handed.
    """

    def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether this matcher claims ``request``.

        Args:
            request: The request that arrived.

        Returns:
            ``True`` when the request is one this matcher claims.
        """
        ...
