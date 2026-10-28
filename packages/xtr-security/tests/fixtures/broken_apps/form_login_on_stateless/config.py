"""A configuration asking for a form login on a stateless firewall."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security.bundle import FormLoginConfig, InMemoryUserProviderConfig, SecurityConfig
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return a configuration the build must refuse."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "hashed", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                provider="users",
                authenticators=(FormLoginConfig(login_path="/login"),),
            )
        },
    )
