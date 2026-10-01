"""Running a firewall's authenticators, and the handlers around a login.

Also the security-level policy that decides which authentication failures are
hidden from the client, and the helpers that apply it.
"""

from __future__ import annotations

from ._sensitive import is_sensitive, mask
from .authentication_failure_handler_interface import AuthenticationFailureHandlerInterface
from .authentication_success_handler_interface import AuthenticationSuccessHandlerInterface
from .authenticator_manager import AuthenticatorManager
from .authenticator_manager_interface import AuthenticatorManagerInterface
from .expose_security_level import ExposeSecurityLevel

__all__ = [
    "AuthenticationFailureHandlerInterface",
    "AuthenticationSuccessHandlerInterface",
    "AuthenticatorManager",
    "AuthenticatorManagerInterface",
    "ExposeSecurityLevel",
    "is_sensitive",
    "mask",
]
