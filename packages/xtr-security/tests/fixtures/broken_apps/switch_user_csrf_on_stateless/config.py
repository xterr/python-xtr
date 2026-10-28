"""A configuration asking for a proven switch on a stateless firewall."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_security.bundle import (
    HttpBasicConfig,
    SecurityConfig,
    SwitchUserConfig,
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
                switch_user=SwitchUserConfig(enable_csrf=True),
                authenticators=(HttpBasicConfig(),),
            )
        },
    )
