"""What drives a firewall's authenticators over one request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http._security_state import SecurityState

__all__ = ["AuthenticatorManagerInterface"]


@runtime_checkable
class AuthenticatorManagerInterface(Protocol):
    """Runs a firewall's authenticators over a request, settling on a token or a failure.

    Asks each authenticator whether it supports the request, parking what the
    pass learned — the supporters, the skipped — on the request's security
    state; the pass that authenticates reads the supporters back off that
    same carrier, so each authenticator is asked once per pass. It then
    authenticates through the first supporter that applies, checks the
    passport, creates and stores the token, and dispatches the events around
    each step. It answers with a response only when a success or failure
    handler produced one; otherwise the request goes on with its token set
    on the storage.
    """

    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        """Tell whether any authenticator handles ``request``, recording the pass.

        The authenticators that support the request and the ones that do not
        are handed to the pass that authenticates through ``state``, the
        request's security state, so they are not asked twice.

        ``None`` means no authenticator is sure yet — a lazy one that would try
        only if a credential were present.
        """
        ...

    async def authenticate_request(
        self, request: ServerRequestInterface, state: SecurityState
    ) -> ResponseInterface | None:
        """Authenticate ``request`` through the supporters the pass recorded.

        Reads — and removes — what the supports pass parked on ``state``; with
        nothing parked, or nothing supporting the request, the request stays
        anonymous.

        Raises:
            AuthenticationError: When authentication fails and no failure
                handler answered it — the firewall turns it into a challenge.
        """
        ...
