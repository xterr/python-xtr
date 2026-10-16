"""What answers a request once its authentication succeeds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationSuccessHandlerInterface"]


@runtime_checkable
class AuthenticationSuccessHandlerInterface(Protocol):
    """Turns a successful authentication into a response, or lets the request go on.

    An authenticator delegates its success reaction here: a handler may answer
    the request itself — a redirect after a form login — or return ``None`` to
    let the request reach its endpoint with the token now set.
    """

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Answer ``request`` for the authenticated ``token``, or return ``None``."""
        ...
