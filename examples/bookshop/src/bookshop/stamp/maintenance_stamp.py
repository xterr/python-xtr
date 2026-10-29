"""A stamp kept in the process: a dispatch the maintenance guard refused."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import NonSendableStampInterface

__all__ = ["MaintenanceStamp"]


@final
@dataclass(frozen=True, slots=True)
class MaintenanceStamp(NonSendableStampInterface):
    """Marks a dispatch the maintenance guard refused.

    Attributes:
        reason: Why.
    """

    reason: str
