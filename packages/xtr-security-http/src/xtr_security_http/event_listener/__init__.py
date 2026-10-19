"""The listeners that resolve a passport, check an account, migrate a hash, rotate a session.

Each is a plain :class:`~xtr_event_dispatcher.EventSubscriberInterface`: the
bundle registers one with ``dispatcher.add_subscriber(listener)`` on a
firewall's own dispatcher, and its declared methods run at the priorities the
authentication sequence needs. The logout listeners answer the logout event
the same way — each does its own part of a logout, at the priority that
orders it around the ones that answer the request. The remember-me pair
answers a login's ask to be remembered — the conditions listener enables
the badge, the listener that follows sets or clears the cookie — and the
endings that must drop one. The throttling listener counts a login's
failed attempts, through a request limiter that builds its own keys.
"""

from __future__ import annotations

from .check_credentials_listener import CheckCredentialsListener
from .check_remember_me_conditions_listener import CheckRememberMeConditionsListener
from .clear_site_data_listener import ClearSiteDataListener
from .cleared_cookie import ClearedCookie
from .cookie_clearing_listener import CookieClearingListener
from .csrf_token_clearing_listener import CsrfTokenClearingListener
from .default_logout_listener import DefaultLogoutListener
from .login_throttling_listener import LoginThrottlingListener
from .password_migrating_listener import PasswordMigratingListener
from .remember_me_listener import RememberMeListener
from .session_logout_listener import SessionLogoutListener
from .session_strategy_listener import SessionStrategyListener
from .user_checker_listener import UserCheckerListener
from .user_provider_listener import UserProviderListener

__all__ = [
    "CheckCredentialsListener",
    "CheckRememberMeConditionsListener",
    "ClearSiteDataListener",
    "ClearedCookie",
    "CookieClearingListener",
    "CsrfTokenClearingListener",
    "DefaultLogoutListener",
    "LoginThrottlingListener",
    "PasswordMigratingListener",
    "RememberMeListener",
    "SessionLogoutListener",
    "SessionStrategyListener",
    "UserCheckerListener",
    "UserProviderListener",
]
