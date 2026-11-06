"""The security configuration the session cookie fixture is built from.

A stateful ``main`` firewall on ``^/`` with a form login and a logout, its
session carried in a ``Secure`` cookie named ``sid`` — what a deployment served
only over HTTPS configures. The login rotates the session (``migrate``, the
default), and the logout invalidates it.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure
from xtr_http_foundation import SessionCookieConfig
from xtr_security_core import InMemoryUser

from xtr_security.bundle import (
    FormLoginConfig,
    InMemoryUserProviderConfig,
    LogoutConfig,
    PlaintextHasherConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["SESSION_COOKIE", "security"]

SESSION_COOKIE: Final = SessionCookieConfig(name="sid", secure=True)
"""The cookie the firewall's session travels in."""


@configure
def security() -> SecurityConfig:
    """Return the session cookie fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "secret", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        # The clear-storage hasher is for tests only; the fixture's login
        # verifies the password as written.
        password_hashers={InMemoryUser: PlaintextHasherConfig()},
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                session_cookie=SESSION_COOKIE,
                logout=LogoutConfig(),
                authenticators=(FormLoginConfig(login_path="/login", post_only=False),),
            )
        },
    )
