"""The event announcing a session token was logged out by its refresh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["TokenDeauthenticatedEvent"]


@final
@dataclass(frozen=True, slots=True)
class TokenDeauthenticatedEvent(Event):
    """Announces that the token read from the session was deauthenticated.

    Dispatched when refreshing the user a session token carried ended in no
    provider vouching for it — the user changed under the session, or no
    provider could find it. A listener clears what the login left behind:
    a remember-me cookie, a session of an upstream provider.

    Attributes:
        original_token: The token as the session stored it, before the
            refresh refused it.
        request: The request the refresh ran for, as a message.
        reason: A sentence explaining the deauthentication, or ``None``.
        provider_classes: The classes of the user providers that contributed
            to the deauthentication decision.
        exception: The authentication error a listener of the refreshed-user
            check gave as its reason, when one did.
    """

    original_token: TokenInterface
    request: ServerRequestInterface
    reason: str | None = None
    provider_classes: tuple[type, ...] = ()
    exception: AuthenticationError | None = None

    def get_original_token(self) -> TokenInterface:
        """Return the token as the session stored it, before the refresh refused it."""
        return self.original_token

    def get_request(self) -> ServerRequestInterface:
        """Return the request the refresh ran for, as a message."""
        return self.request

    def get_reason(self) -> str | None:
        """Return the sentence explaining the deauthentication, if there is one."""
        return self.reason

    def get_provider_classes(self) -> tuple[type, ...]:
        """Return the user providers that contributed to the deauthentication."""
        return self.provider_classes

    def get_exception(self) -> AuthenticationError | None:
        """Return the error a refreshed-user listener gave as its reason, if one did."""
        return self.exception
