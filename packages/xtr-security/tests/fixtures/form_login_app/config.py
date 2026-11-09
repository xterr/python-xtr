"""The security configuration the form-login fixture is built from.

A stateful ``main`` firewall on ``^/`` with a form login — its fields read
from the posted body alone, ``post_only`` standing — a logout and a switch-user
block, and ahead of it a stateful ``api`` firewall on ``^/api`` with a JSON
login. Both load their users from one in-memory provider: ``ada``, who may
switch, and ``bob``, who may not, their passwords checked as written.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security_core import InMemoryUser

from xtr_security.bundle import (
    FormLoginConfig,
    InMemoryUserProviderConfig,
    JsonLoginConfig,
    LogoutConfig,
    PlaintextHasherConfig,
    SecurityConfig,
    SwitchUserConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the form-login fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={
                    "ada": {
                        "password": "secret",
                        "roles": ["ROLE_USER", "ROLE_ALLOWED_TO_SWITCH"],
                        "enabled": True,
                    },
                    "bob": {"password": "secret", "roles": ["ROLE_USER"], "enabled": True},
                }
            )
        },
        # The clear-storage hasher is for tests only; the fixture's logins
        # verify the password as written.
        password_hashers={InMemoryUser: PlaintextHasherConfig()},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                stateless=False,
                provider="users",
                authenticators=(JsonLoginConfig(check_path="/api/login"),),
            ),
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                logout=LogoutConfig(),
                switch_user=SwitchUserConfig(),
                authenticators=(FormLoginConfig(login_path="/login"),),
            ),
        },
    )
