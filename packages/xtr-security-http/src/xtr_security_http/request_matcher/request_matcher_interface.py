"""What decides whether a firewall's access rule claims a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["RequestMatcherInterface"]


@runtime_checkable
class RequestMatcherInterface(Protocol):
    """Answers whether a request is the one an access rule applies to.

    An access map pairs a matcher with the attribute a matching request must
    hold; the first matcher that claims a request decides it. A matcher reads
    only the request — its path, method, host or client address — never the
    token, which the decision that follows is about.
    """

    def matches(self, request: Request) -> bool:
        """Tell whether this matcher claims ``request``."""
        ...
