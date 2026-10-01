"""What turns an access denial into a response of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.exception import AccessDeniedError

__all__ = ["AccessDeniedHandlerInterface"]


@runtime_checkable
class AccessDeniedHandlerInterface(Protocol):
    """Shapes the response to a caller who is known but not allowed.

    A firewall hands a denial here when the caller is fully authenticated —
    the answer is a refusal, not a challenge. A handler may return a response
    of its own, or ``None`` to leave the firewall to answer with a plain
    ``403``.
    """

    async def handle(self, request: Request, error: AccessDeniedError) -> Response | None:
        """Return the response that refuses ``request``, or ``None`` for a plain refusal."""
        ...
