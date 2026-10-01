"""What starts authentication when a request reaches a protected resource unauthenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.exception import AuthenticationError

__all__ = ["AuthenticationEntryPointInterface"]


@runtime_checkable
class AuthenticationEntryPointInterface(Protocol):
    """Answers an unauthenticated request with what it takes to authenticate.

    When a request reaches a protected resource without proving who is calling,
    the firewall's entry point turns that into a response: a ``401`` carrying
    the challenge a bearer scheme expects, a redirect to a login form. The
    error that led here, when there is one, shapes the challenge.
    """

    async def start(self, request: Request, error: AuthenticationError | None = None) -> Response:
        """Return the response that asks ``request`` to authenticate.

        Args:
            request: The request that reached a protected resource.
            error: The authentication error that led here, when one did, so the
                challenge can name why — a bad token, insufficient scope.
        """
        ...
