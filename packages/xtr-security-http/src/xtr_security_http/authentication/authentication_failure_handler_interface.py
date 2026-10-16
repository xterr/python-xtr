"""What answers a request once its authentication fails."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
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
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Answer ``request`` for the failure ``error``, or return ``None``."""
        ...
