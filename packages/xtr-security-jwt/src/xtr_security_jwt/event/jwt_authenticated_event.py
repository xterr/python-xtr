"""The event carrying a token's payload and the token it authenticated into."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["JwtAuthenticatedEvent"]


@final
class JwtAuthenticatedEvent(Event):
    """Announces that a token authenticated a request, with its payload.

    Dispatched by the authenticator once a token settled on a security token. A
    listener may inspect the payload, or reject the request by raising — the seam
    a revocation check reaches for.
    """

    __slots__ = ("_payload", "_token")

    def __init__(self, payload: dict[str, object], token: TokenInterface) -> None:
        """Record the token's ``payload`` and the security ``token`` it settled on."""
        self._payload = payload
        self._token = token

    def get_payload(self) -> dict[str, object]:
        """Return the verified token's claims, open to change."""
        return self._payload

    def set_payload(self, payload: dict[str, object]) -> None:
        """Replace the verified token's claims."""
        self._payload = payload

    def get_token(self) -> TokenInterface:
        """Return the security token the request authenticated into."""
        return self._token
