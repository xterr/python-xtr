"""The errors the HTTP edge adds to the security core's.

Each derives from a core error — :class:`~xtr_security_core.exception.SecurityError`
or :class:`~xtr_security_core.exception.AuthenticationError` — so one
``except SecurityError`` still catches everything the family raises.
The one base here that is not itself an error is the login-link marker:
never raised, only worn by the refusals a link earns so the flow catches
them together.
"""

from __future__ import annotations

from .expired_login_link_error import ExpiredLoginLinkError
from .impersonation_error import ImpersonationError
from .invalid_access_token_error import InvalidAccessTokenError
from .invalid_csrf_token_error import InvalidCsrfTokenError
from .invalid_login_link_authentication_error import InvalidLoginLinkAuthenticationError
from .invalid_login_link_error import InvalidLoginLinkError
from .invalid_login_link_error_interface import InvalidLoginLinkErrorInterface
from .invalid_session_strategy_error import InvalidSessionStrategyError
from .logout_error import LogoutError
from .missing_session_error import MissingSessionError
from .missing_state_bag_error import MissingStateBagError
from .oidc_invalid_grant_error import OidcInvalidGrantError
from .unknown_firewall_error import UnknownFirewallError

__all__ = [
    "ExpiredLoginLinkError",
    "ImpersonationError",
    "InvalidAccessTokenError",
    "InvalidCsrfTokenError",
    "InvalidLoginLinkAuthenticationError",
    "InvalidLoginLinkError",
    "InvalidLoginLinkErrorInterface",
    "InvalidSessionStrategyError",
    "LogoutError",
    "MissingSessionError",
    "MissingStateBagError",
    "OidcInvalidGrantError",
    "UnknownFirewallError",
]
