"""A configuration asking for a proven logout on a stateless firewall."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security.bundle import (
    HttpBasicConfig,
    LogoutConfig,
    SecurityConfig,
)
from xtr_security.firewall_config import FirewallConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return a configuration the build must refuse."""
    return SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                pattern=r"^/",
                logout=LogoutConfig(enable_csrf=True),
                authenticators=(HttpBasicConfig(),),
            )
        },
    )
