"""The one question every matcher answers about a request that arrived."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["RequestMatcherInterface"]


@runtime_checkable
class RequestMatcherInterface(Protocol):
    """Decides whether the rule a matcher stands for holds for a request.

    One matcher constrains one thing — the method, the path, the address it came
    from — so what a firewall, an endpoint or a limiter claims is a value it can
    be handed rather than a condition written into it, and a chain of them says
    the whole of it.
    """

    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether this matcher claims ``request``.

        Awaited because a rule may be about the body, which arrives as it is
        read. A matcher that only reads the head of the request still answers
        this way, so one can be swapped for another.

        Args:
            request: The request that arrived.

        Returns:
            ``True`` when the request is one this matcher claims.
        """
        ...
