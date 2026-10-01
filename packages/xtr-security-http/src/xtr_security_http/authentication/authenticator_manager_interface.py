"""What drives a firewall's authenticators over one request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["AuthenticatorManagerInterface"]


@runtime_checkable
class AuthenticatorManagerInterface(Protocol):
    """Runs a firewall's authenticators over a request, settling on a token or a failure.

    Asks each authenticator whether it supports the request, authenticates
    through the first that does, checks the passport, creates and stores the
    token, and dispatches the events around each step. It answers with a
    response only when a success or failure handler produced one; otherwise the
    request goes on with its token set on the storage.
    """

    def supports(self, request: Request) -> bool | None:
        """Tell whether any authenticator handles ``request``.

        ``None`` means no authenticator is sure yet — a lazy one that would try
        only if a credential were present.
        """
        ...

    async def authenticate_request(self, request: Request) -> Response | None:
        """Authenticate ``request``, returning a handler's response if one answered.

        Raises:
            AuthenticationError: When authentication fails and no failure
                handler answered it — the firewall turns it into a challenge.
        """
        ...
