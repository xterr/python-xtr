"""What answers a request once its authentication fails."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.exception import AuthenticationError

__all__ = ["AuthenticationFailureHandlerInterface"]


@runtime_checkable
class AuthenticationFailureHandlerInterface(Protocol):
    """Turns a failed authentication into a response, or leaves it to the entry point.

    An authenticator delegates its failure reaction here: a handler may answer
    the request itself — a challenge, a redirect back to a form — or return
    ``None`` to let the failure carry on and be turned into a response by the
    firewall's entry point.
    """

    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        """Answer ``request`` for the failure ``error``, or return ``None``."""
        ...
