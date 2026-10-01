"""The enrichment that stamps a unique id onto every token."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_jwt.services.payload_enrichment_interface import PayloadEnrichmentInterface

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["RandomJtiEnrichment"]


@final
class RandomJtiEnrichment(PayloadEnrichmentInterface):
    """Adds a random ``jti`` to a payload, so every token has a unique id.

    The id a deployment needs to refer to one token — to revoke it — added to
    every token it mints.
    """

    __slots__ = ()

    @override
    def enrich(self, user: UserInterface, payload: dict[str, object]) -> None:
        """Stamp a random hexadecimal ``jti`` onto the payload."""
        del user
        payload["jti"] = secrets.token_hex(16)
