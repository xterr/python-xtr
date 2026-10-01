"""The listeners that resolve a passport, check an account, and migrate a hash.

Each is a plain :class:`~xtr_event_dispatcher.EventSubscriberInterface`: the
bundle registers one with ``dispatcher.add_subscriber(listener)`` on a
firewall's own dispatcher, and its declared methods run at the priorities the
authentication sequence needs.
"""

from __future__ import annotations

from .check_credentials_listener import CheckCredentialsListener
from .password_migrating_listener import PasswordMigratingListener
from .user_checker_listener import UserCheckerListener
from .user_provider_listener import UserProviderListener

__all__ = [
    "CheckCredentialsListener",
    "PasswordMigratingListener",
    "UserCheckerListener",
    "UserProviderListener",
]
