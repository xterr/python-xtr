"""A stamp of the application's own: what a middleware records on an envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import NonSendableStampInterface

__all__ = ["DispatchTimeStamp", "MaintenanceStamp"]


@final
@dataclass(frozen=True, slots=True)
class DispatchTimeStamp(NonSendableStampInterface):
    """How long the rest of the chain took, recorded by ``TimingMiddleware``.

    ``NonSendableStampInterface``: stripped before the envelope reaches a transport, so it
    never travels on the wire — a local measurement means nothing to a consumer.

    Attributes:
        milliseconds: The duration.
    """

    milliseconds: float


@final
@dataclass(frozen=True, slots=True)
class MaintenanceStamp(NonSendableStampInterface):
    """Marks a dispatch the maintenance guard refused.

    Attributes:
        reason: Why.
    """

    reason: str
