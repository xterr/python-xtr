"""The errors the HTTP edge adds to the security core's.

Each derives from a core error — :class:`~xtr_security_core.exception.SecurityError`
or :class:`~xtr_security_core.exception.AuthenticationError` — so one
``except SecurityError`` still catches everything the family raises.
"""

from __future__ import annotations

from .invalid_access_token_error import InvalidAccessTokenError
from .invalid_session_strategy_error import InvalidSessionStrategyError
from .missing_session_error import MissingSessionError
from .missing_state_bag_error import MissingStateBagError
from .unknown_firewall_error import UnknownFirewallError

__all__ = [
    "InvalidAccessTokenError",
    "InvalidSessionStrategyError",
    "MissingSessionError",
    "MissingStateBagError",
    "UnknownFirewallError",
]
