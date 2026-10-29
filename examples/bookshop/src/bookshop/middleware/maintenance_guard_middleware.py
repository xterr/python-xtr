"""A middleware instance built in the config, not named: the maintenance guard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override
from xtr_messenger import Envelope, MiddlewareInterface, StackInterface

from bookshop.message.place_order import PlaceOrder
from bookshop.stamp.maintenance_stamp import MaintenanceStamp

__all__ = ["MaintenanceGuard"]


@final
@dataclass(frozen=True, slots=True)
class MaintenanceGuard(MiddlewareInterface):
    """Refuses new orders while the shop is in maintenance — built in the config.

    Its ``enabled`` field is an ``env("SHOP_MAINTENANCE", bool, ...)`` placeholder while the
    kernel builds; the container resolves the whole config, this dataclass included, before
    the bus receives it. Returning the envelope without calling the next middleware
    short-circuits the chain: nothing downstream runs.

    Attributes:
        enabled: Whether to refuse.
    """

    enabled: bool

    @override
    async def handle(self, envelope: Envelope, stack: StackInterface, /) -> Envelope:
        if self.enabled and isinstance(envelope.message, PlaceOrder):
            return envelope.with_stamps(MaintenanceStamp("the shop is in maintenance"))
        return await stack.next().handle(envelope, stack)
