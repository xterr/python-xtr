"""The listeners that resolve a passport, check an account, migrate a hash, rotate a session.

Each is a plain :class:`~xtr_event_dispatcher.EventSubscriberInterface`: the
bundle registers one with ``dispatcher.add_subscriber(listener)`` on a
firewall's own dispatcher, and its declared methods run at the priorities the
authentication sequence needs. The logout listeners answer the logout event
the same way — each does its own part of a logout, at the priority that
orders it around the ones that answer the request.
"""

from __future__ import annotations

from .check_credentials_listener import CheckCredentialsListener
from .clear_site_data_listener import ClearSiteDataListener
from .cleared_cookie import ClearedCookie
from .cookie_clearing_listener import CookieClearingListener
from .csrf_token_clearing_listener import CsrfTokenClearingListener
from .default_logout_listener import DefaultLogoutListener
from .password_migrating_listener import PasswordMigratingListener
from .session_logout_listener import SessionLogoutListener
from .session_strategy_listener import SessionStrategyListener
from .user_checker_listener import UserCheckerListener
from .user_provider_listener import UserProviderListener

__all__ = [
    "CheckCredentialsListener",
    "ClearSiteDataListener",
    "ClearedCookie",
    "CookieClearingListener",
    "CsrfTokenClearingListener",
    "DefaultLogoutListener",
    "PasswordMigratingListener",
    "SessionLogoutListener",
    "SessionStrategyListener",
    "UserCheckerListener",
    "UserProviderListener",
]
