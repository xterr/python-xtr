"""Each unit of work starts reading from the replicas, whatever the unit around it wrote."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, cast, final

from advanced_alchemy.routing import stick_to_primary_var

if TYPE_CHECKING:
    from contextvars import Token

__all__ = ["StickinessParticipant"]


@final
class StickinessParticipant:
    """Starts every unit of work on the replicas, and leaves the unit around it as it was.

    On a connection with replicas, a write sends every later read of the unit
    to the primary, so it reads what it wrote. That is one unit's state: a
    new unit starts on the replicas again, and when it ends the unit around
    it — a request a message was handled inside — is back where it was, on
    the primary if it had written.

    Told of each unit by the container — it is a unit participant — and
    registered by the orm bundle only when a connection has replicas.
    """

    __slots__ = ()

    def unit_began(self) -> object | None:
        """Read from the replicas until the new unit writes."""
        return stick_to_primary_var.set(False)

    def unit_ended(self, token: object | None) -> None:
        """Put back what the unit around this one read from."""
        # The container hands back what unit_began returned for this unit.
        began = cast("Token[bool]", token)
        # Refused when the unit ends in another context than it began in:
        # that one never held this unit's value, so there is nothing to restore.
        with suppress(ValueError):
            stick_to_primary_var.reset(began)
