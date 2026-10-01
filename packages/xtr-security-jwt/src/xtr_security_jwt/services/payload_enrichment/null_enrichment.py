"""The enrichment that adds nothing, the token manager's default."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["NullEnrichment"]


@final
class NullEnrichment(PayloadEnrichmentInterface):
    """Adds no claims, the enrichment a token manager uses when none is configured."""

    __slots__ = ()

    @override
    def enrich(self, user: UserInterface, payload: dict[str, object]) -> None:
        """Add nothing to the payload."""
        del user, payload
