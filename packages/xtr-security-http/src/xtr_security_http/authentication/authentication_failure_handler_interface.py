"""What answers a request once its authentication fails."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["AuthenticationFailureHandlerInterface"]


@runtime_checkable
class AuthenticationFailureHandlerInterface(Protocol):
    """Turns a failed authentication into the response that answers it.

    An authenticator delegates its failure reaction here: a handler answers
    the request itself — a challenge, a redirect back to a form — and the
    response it returns is what the firewall sends. A handler that wants the
    entry point's challenge instead is not a failure handler: the authenticator
    answers with ``None`` when it has none.
    """

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Answer ``request`` for the failure ``error``."""
        ...
