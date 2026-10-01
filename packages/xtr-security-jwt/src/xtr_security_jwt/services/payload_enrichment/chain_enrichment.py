"""The enrichment that runs several enrichments in turn."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["ChainEnrichment"]


@final
class ChainEnrichment(PayloadEnrichmentInterface):
    """Runs each of several enrichments over the payload, in order.

    The one the token manager is given: the bundle collects every registered
    enrichment into it, so a payload passes through all of them before it is
    signed.
    """

    __slots__ = ("_enrichments",)

    def __init__(self, enrichments: Sequence[PayloadEnrichmentInterface]) -> None:
        """Record the enrichments to run, in order."""
        self._enrichments = tuple(enrichments)

    @override
    def enrich(self, user: UserInterface, payload: dict[str, object]) -> None:
        """Run each enrichment over the payload in turn."""
        for enrichment in self._enrichments:
            enrichment.enrich(user, payload)
