"""The errors the HTTP edge adds to the security core's.

Each derives from a core error — :class:`~xtr_security_core.exception.SecurityError`
or :class:`~xtr_security_core.exception.AuthenticationError` — so one
``except SecurityError`` still catches everything the family raises.
"""

from __future__ import annotations

from .firewall_not_booted_error import FirewallNotBootedError
from .invalid_access_token_error import InvalidAccessTokenError
from .unknown_firewall_error import UnknownFirewallError

__all__ = [
    "FirewallNotBootedError",
    "InvalidAccessTokenError",
    "UnknownFirewallError",
]
