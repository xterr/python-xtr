"""A stateful firewall with no session storage: the build must refuse it.

The fixture registers no ``SessionStorageInterface`` service, so the
context listener the stateful wiring registers is dropped by the
remove-if-missing marker, and the bundle's guard pass fails the build
naming the missing service.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security.bundle import (
    HttpBasicConfig,
    InMemoryUserProviderConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the broken fixture's security configuration."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={"alice": {"password": "hashed", "roles": ["ROLE_USER"], "enabled": True}}
            )
        },
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                authenticators=(HttpBasicConfig(),),
            )
        },
    )
