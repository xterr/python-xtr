"""A stateful firewall whose form login and logout paths are environment variables."""

from __future__ import annotations

from xtr_dependency_injection import configure, env
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
    """Return the fixture's security configuration, every path read from the environment."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "secret", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        password_hashers={InMemoryUser: PlaintextHasherConfig()},
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                logout=LogoutConfig(path=env("LOGOUT_PATH"), target_path=env("WEB_APP_ORIGIN")),
                authenticators=(
                    FormLoginConfig(
                        login_path=env("LOGIN_PATH"),
                        check_path=env("CHECK_PATH"),
                        post_only=False,
                    ),
                ),
            )
        },
    )
