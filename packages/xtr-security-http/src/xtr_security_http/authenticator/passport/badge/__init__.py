"""The badges a passport carries: the user, and notes about the authentication."""

from __future__ import annotations

from .authentication_method_badge import AuthenticationMethodBadge
from .badge_interface import BadgeInterface
from .csrf_token_badge import CsrfTokenBadge
from .password_upgrade_badge import PasswordUpgradeBadge
from .pre_authenticated_user_badge import PreAuthenticatedUserBadge
from .remember_me_badge import RememberMeBadge
from .user_badge import MAX_USERNAME_LENGTH, UserBadge

__all__ = [
    "MAX_USERNAME_LENGTH",
    "AuthenticationMethodBadge",
    "BadgeInterface",
    "CsrfTokenBadge",
    "PasswordUpgradeBadge",
    "PreAuthenticatedUserBadge",
    "RememberMeBadge",
    "UserBadge",
]
