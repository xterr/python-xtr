"""A stamp kept in the process: how long a dispatch took."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import NonSendableStampInterface

__all__ = ["DispatchTimeStamp"]


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
