"""Every error the security core raises.

All of them derive from :class:`SecurityError`, so one ``except`` catches
anything authentication or authorization can go wrong with, and a narrower one
handles a single cause. Each carries the data a caller needs as typed
attributes rather than forcing a message to be parsed. The HTTP edge adds its
own errors that still derive from these.
"""

from __future__ import annotations

from .access_denied_error import AccessDeniedError
from .account_expired_error import AccountExpiredError
from .account_status_error import AccountStatusError
from .authentication_credentials_not_found_error import AuthenticationCredentialsNotFoundError
from .authentication_error import AuthenticationError
from .authentication_service_error import AuthenticationServiceError
from .bad_credentials_error import BadCredentialsError
from .credentials_expired_error import CredentialsExpiredError
from .custom_user_message_account_status_error import CustomUserMessageAccountStatusError
from .custom_user_message_authentication_error import CustomUserMessageAuthenticationError
from .disabled_error import DisabledError
from .insufficient_authentication_error import InsufficientAuthenticationError
from .invalid_argument_error import InvalidArgumentError
from .locked_error import LockedError
from .security_error import SecurityError
from .unsupported_user_error import UnsupportedUserError
from .user_not_found_error import UserNotFoundError

__all__ = [
    "AccessDeniedError",
    "AccountExpiredError",
    "AccountStatusError",
    "AuthenticationCredentialsNotFoundError",
    "AuthenticationError",
    "AuthenticationServiceError",
    "BadCredentialsError",
    "CredentialsExpiredError",
    "CustomUserMessageAccountStatusError",
    "CustomUserMessageAuthenticationError",
    "DisabledError",
    "InsufficientAuthenticationError",
    "InvalidArgumentError",
    "LockedError",
    "SecurityError",
    "UnsupportedUserError",
    "UserNotFoundError",
]
