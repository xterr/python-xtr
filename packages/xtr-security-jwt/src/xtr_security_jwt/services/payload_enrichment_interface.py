"""What adds claims to a token payload before it is signed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["PayloadEnrichmentInterface"]


@runtime_checkable
class PayloadEnrichmentInterface(Protocol):
    """Adds claims to a token payload, in place, before it is signed.

    The token manager calls one after it has assembled the user's identity and
    roles, so a deployment can stamp a claim onto every token it mints — a unique
    id, a tenant — without a listener. The payload is edited in place.
    """

    def enrich(self, user: UserInterface, payload: dict[str, object]) -> None:
        """Add to ``payload`` the claims ``user``'s token should carry."""
        ...
