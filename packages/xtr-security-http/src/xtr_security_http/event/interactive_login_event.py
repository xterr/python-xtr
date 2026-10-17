"""The event announcing a user's own, interactive login."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["InteractiveLoginEvent"]


@dataclass(frozen=True)
class InteractiveLoginEvent(Event):
    """Announces a user's own, interactive login.

    A user actively authenticated — a form submitted, a login link followed —
    as opposed to a session or a bearer token re-establishing the same user
    passively. Dispatched under
    :attr:`~xtr_security_http.security_events.SecurityEvents.INTERACTIVE_LOGIN`
    — the one event here that carries a name of its own, because an
    application listens for it across the whole flow rather than at one
    authenticator — after an interactive authenticator's success handler ran
    and before the login-success event. A listener reads the request the user
    acted through and the token their login settled on, to stamp a session or
    write an audit line; the token is the one the storage now holds, and
    cannot be replaced from here.

    Attributes:
        request: The request the user logged in through.
        token: The token the login settled on.
    """

    request: ServerRequestInterface
    token: TokenInterface

    def get_request(self) -> ServerRequestInterface:
        """Return the request the user logged in through."""
        return self.request

    def get_authenticated_token(self) -> TokenInterface:
        """Return the token the login settled on."""
        return self.token
