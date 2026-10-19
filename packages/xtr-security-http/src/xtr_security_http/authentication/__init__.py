"""Running a firewall's authenticators, and the handlers around a login.

Also the security-level policy that decides which authentication failures are
hidden from the client, and the helpers that apply it.
"""

from __future__ import annotations

from ._sensitive import is_sensitive, mask
from .authentication_failure_handler_interface import AuthenticationFailureHandlerInterface
from .authentication_success_handler_interface import AuthenticationSuccessHandlerInterface
from .authentication_utils import AuthenticationUtils
from .authenticator_manager import AuthenticatorManager
from .authenticator_manager_interface import AuthenticatorManagerInterface
from .custom_authentication_failure_handler import CustomAuthenticationFailureHandler
from .custom_authentication_success_handler import CustomAuthenticationSuccessHandler
from .default_authentication_failure_handler import DefaultAuthenticationFailureHandler
from .default_authentication_success_handler import DefaultAuthenticationSuccessHandler
from .expose_security_level import ExposeSecurityLevel
from .user_authenticator_interface import UserAuthenticatorInterface

__all__ = [
    "AuthenticationFailureHandlerInterface",
    "AuthenticationSuccessHandlerInterface",
    "AuthenticationUtils",
    "AuthenticatorManager",
    "AuthenticatorManagerInterface",
    "CustomAuthenticationFailureHandler",
    "CustomAuthenticationSuccessHandler",
    "DefaultAuthenticationFailureHandler",
    "DefaultAuthenticationSuccessHandler",
    "ExposeSecurityLevel",
    "UserAuthenticatorInterface",
    "is_sensitive",
    "mask",
]
