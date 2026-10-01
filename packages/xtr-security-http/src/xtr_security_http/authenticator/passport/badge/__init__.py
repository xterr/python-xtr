"""The badges a passport carries: the user, and notes about the authentication."""

from __future__ import annotations

from .badge_interface import BadgeInterface
from .password_upgrade_badge import PasswordUpgradeBadge
from .pre_authenticated_user_badge import PreAuthenticatedUserBadge
from .user_badge import MAX_USERNAME_LENGTH, UserBadge

__all__ = [
    "MAX_USERNAME_LENGTH",
    "BadgeInterface",
    "PasswordUpgradeBadge",
    "PreAuthenticatedUserBadge",
    "UserBadge",
]
