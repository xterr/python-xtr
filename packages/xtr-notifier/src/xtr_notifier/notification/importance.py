"""How much a notification matters."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Importance"]


class Importance(StrEnum):
    """How much a notification matters, which a channel policy maps to channels.

    String values, so a policy configured with plain strings (``{"urgent":
    ["sms", "chat"]}``) matches an importance without a conversion step.
    """

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
