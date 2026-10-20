"""The security configuration the CSRF fixture is built from.

A stateful ``main`` firewall on ``^/`` with a form login whose form carries a
forgery token, and a logout that both demands one and drops the stored ones —
 every piece of the forgery machinery the bundle wires, on one firewall.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from xtr_security.bundle import (
    FormLoginConfig,
    InMemoryUserProviderConfig,
    LogoutConfig,
    PlaintextHasherConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the CSRF fixture's security configuration."""
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
                logout=LogoutConfig(enable_csrf=True, clear_csrf_tokens=True),
                authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),),
            )
        },
    )
