"""The shop's service tier — read from the environment as an enum member."""

from __future__ import annotations

from enum import Enum

__all__ = ["Tier"]


class Tier(Enum):
    """Which plan the shop runs on; ``SHOP_TIER`` holds the value."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
